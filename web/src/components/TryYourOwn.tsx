import { useEffect, useRef, useState } from 'react'
import { kb } from '../site'

// Everything here happens on the visitor's own device. The photograph is read by the browser,
// redrawn on a canvas and saved as a JPEG in memory. Nothing is sent anywhere and nothing is
// kept after the page is closed.

const APP_SIDE = 1080 // the photo app's longest side, as in my own runs
const APP_QUALITY = 0.72
const PHONE = { w: 1170, h: 2532 }
const PASSES = 20
const KEEP = [1, 5, 10, 20]

type Hidden = { camera: string | null; date: boolean; location: boolean } | 'none' | 'unknown'
type Result = { pass: number; url: string; bytes: number }

/** Look inside a JPEG for the details a camera saves with it. Reads only the start of the file. */
function hiddenDetails(buf: ArrayBuffer): Hidden {
  const v = new DataView(buf)
  if (v.byteLength < 4 || v.getUint16(0) !== 0xffd8) return 'unknown' // not a JPEG
  let at = 2
  while (at + 4 <= v.byteLength) {
    const marker = v.getUint16(at)
    const size = v.getUint16(at + 2)
    if ((marker & 0xff00) !== 0xff00) break
    if (marker === 0xffe1 && at + 10 <= v.byteLength && v.getUint32(at + 4) === 0x45786966) {
      const tiff = at + 10
      if (tiff + 8 > v.byteLength) return 'unknown'
      const little = v.getUint16(tiff) === 0x4949
      const ifd = tiff + v.getUint32(tiff + 4, little)
      if (ifd + 2 > v.byteLength) return 'unknown'
      const count = v.getUint16(ifd, little)
      let camera: string | null = null, date = false, location = false
      for (let i = 0; i < count; i++) {
        const entry = ifd + 2 + i * 12
        if (entry + 12 > v.byteLength) break
        const tag = v.getUint16(entry, little)
        if (tag === 0x8825) location = true // a pointer to GPS data
        if (tag === 0x0132) date = true
        if (tag === 0x8769) date = true // the block that holds the time the picture was taken
        if (tag === 0x0110) {
          const length = v.getUint32(entry + 4, little)
          const start = length <= 4 ? entry + 8 : tiff + v.getUint32(entry + 8, little)
          if (start + length <= v.byteLength) {
            let text = ''
            for (let k = 0; k < length - 1; k++) text += String.fromCharCode(v.getUint8(start + k))
            camera = text.trim() || null
          }
        }
      }
      return { camera, date, location }
    }
    if (marker === 0xffda) break // the picture itself starts here
    at += 2 + size
  }
  return 'none'
}

const fit = (w: number, h: number, maxW: number, maxH: number, grow: boolean) => {
  const scale = Math.min(maxW / w, maxH / h)
  const s = grow ? scale : Math.min(1, scale)
  return { w: Math.max(1, Math.round(w * s)), h: Math.max(1, Math.round(h * s)) }
}

function draw(source: CanvasImageSource, w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d')
  if (!ctx) throw new Error('This browser cannot draw the picture.')
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(source, 0, 0, w, h)
  return c
}

const toJpeg = (c: HTMLCanvasElement) =>
  new Promise<Blob>((resolve, reject) => c.toBlob((b) => (b ? resolve(b) : reject(new Error('This browser could not save the picture.'))), 'image/jpeg', APP_QUALITY))

export default function TryYourOwn() {
  const [screenshot, setScreenshot] = useState(true)
  const [file, setFile] = useState<File | null>(null)
  const [hidden, setHidden] = useState<Hidden | null>(null)
  const [results, setResults] = useState<Result[]>([])
  const [shown, setShown] = useState(0)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const urls = useRef<string[]>([])
  const run = useRef(0)

  const forget = () => {
    urls.current.forEach((u) => URL.revokeObjectURL(u))
    urls.current = []
  }
  useEffect(() => forget, [])

  useEffect(() => {
    if (!file) return
    const mine = ++run.current
    const stale = () => mine !== run.current
    forget()
    setResults([])
    setError('')
    setStatus('Reading your photo…')
    ;(async () => {
      try {
        setHidden(hiddenDetails(await file.slice(0, 262144).arrayBuffer()))
        let picture: ImageBitmap = await createImageBitmap(file)
        const first = URL.createObjectURL(file)
        urls.current.push(first)
        const made: Result[] = [{ pass: 0, url: first, bytes: file.size }]
        for (let pass = 1; pass <= PASSES; pass++) {
          if (stale()) return
          setStatus(`Pass ${pass} of ${PASSES}…`)
          let source: CanvasImageSource = picture
          let w = picture.width, h = picture.height
          if (screenshot) {
            const onScreen = fit(w, h, PHONE.w, PHONE.h, true) // a phone shows it as large as fits
            source = draw(picture, onScreen.w, onScreen.h)
            w = onScreen.w
            h = onScreen.h
          }
          const uploaded = fit(w, h, APP_SIDE, APP_SIDE, false) // the app only ever shrinks
          const blob = await toJpeg(draw(source, uploaded.w, uploaded.h))
          picture.close()
          picture = await createImageBitmap(blob)
          if (KEEP.includes(pass)) {
            const url = URL.createObjectURL(blob)
            urls.current.push(url)
            made.push({ pass, url, bytes: blob.size })
          }
          await new Promise((r) => setTimeout(r)) // let the page breathe between passes
        }
        picture.close()
        if (stale()) return
        setResults(made)
        setShown(made.length - 1)
        setStatus(`Done: ${PASSES} passes.`)
      } catch (e) {
        if (stale()) return
        setStatus('')
        setError(e instanceof Error && e.message ? `That did not work. ${e.message} Try a JPEG or PNG photo.` : 'That did not work. Try a JPEG or PNG photo.')
      }
    })()
  }, [file, screenshot])

  const current = results[shown]
  return (
    <div className="try">
      <p>
        Your photo stays on this device. The page does the passes inside your browser. Nothing is uploaded and nothing is kept
        when you close the page.
      </p>
      <div className="try-controls">
        <label className="file">
          <span>Choose a photo</span>
          <input type="file" name="photo" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <label className="check">
          <input type="checkbox" name="screenshot" checked={screenshot} onChange={(e) => setScreenshot(e.target.checked)} />
          Screenshot it before each upload
        </label>
      </div>
      <p className="small muted" role="status" aria-live="polite">{status}</p>
      {error && <p className="small error" role="alert">{error}</p>}

      {hidden && file && (
        <p>
          {hidden === 'unknown' && 'I can only look for hidden details in JPEG files, and this is not one.'}
          {hidden === 'none' && 'Your browser handed this photo to the page with no hidden details in it. Some phones remove them when you pick a photo.'}
          {typeof hidden === 'object' && (
            <>
              This file carries hidden details{hidden.camera ? `: it says it was taken with ${hidden.camera}` : ''}
              {hidden.date ? ', it holds a date' : ''}
              {hidden.location ? ', and it holds a location' : ', and no location'}. After one pass they are all gone.
            </>
          )}
        </p>
      )}

      {current && (
        <>
          <div className="stage">
            <img src={current.url} alt={current.pass === 0 ? 'Your photo as you chose it.' : `Your photo after ${current.pass} ${current.pass === 1 ? 'pass' : 'passes'}.`} />
            <span className="tag">{current.pass === 0 ? 'Your photo' : `Pass ${current.pass} of ${PASSES}`}</span>
          </div>
          <div className="controls">
            <div className="stops" role="group" aria-label="Go to a pass of your photo">
              {results.map((r, i) => (
                <button key={r.pass} className={i === shown ? 'current' : ''} aria-current={i === shown ? 'step' : undefined} onClick={() => setShown(i)}>
                  {r.pass === 0 ? 'Yours' : r.pass}
                </button>
              ))}
            </div>
            <span className="small muted">{kb(current.bytes)}{current.pass > 0 ? `, from ${kb(results[0].bytes)}` : ''}</span>
          </div>
          <p className="small faint">
            Your browser does the shrinking and saving in its own way, so these numbers will not match mine exactly.
          </p>
        </>
      )}
    </div>
  )
}
