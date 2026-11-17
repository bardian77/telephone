import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import DetailLine from '../components/DetailLine'
import TryYourOwn from '../components/TryYourOwn'
import { JOURNEYS, PHOTOS, dataUrl, kb, percent, shortPlace, type Journey, type Site, type SitePass, type SitePhoto } from '../site'

type Focus = { x: number; y: number } // a point on the original, as fractions of its width and height
type Row = { term: string; state: 'here' | 'going' | 'gone' | 'plain'; text: string }

const STATE_WORD = { here: 'still here', going: 'going', gone: 'gone', plain: '' } as const
const LOUPE = 220 // CSS pixels

/** Where a point of the original sits in this pass's picture, as fractions of the picture. */
function inPicture(p: SitePass, photo: SitePhoto, f: Focus) {
  const [x0, y0, x1, y1] = p.detail?.box ?? [0, 0, photo.width, photo.height]
  const u = (f.x * photo.width - x0) / (x1 - x0), v = (f.y * photo.height - y0) / (y1 - y0)
  // out of the frame: a careless crop has cut this spot away
  return { u, v, across: (x1 - x0) / photo.width, cut: u < 0 || u > 1 || v < 0 || v > 1 }
}

function Loupe({ p, photo, focus, reference }: { p: SitePass; photo: SitePhoto; focus: Focus; reference: number }) {
  if (!p.width || !p.height) return null
  const { u, v, across, cut } = inPicture(p, photo, focus)
  if (cut) return <div className="loupe cut"><span>This spot has been cropped out of the frame.</span></div>
  // Show the same piece of the scene at every pass. At pass 1 that piece is LOUPE pixels of the
  // file, drawn one to one.
  const shareOfPicture = LOUPE / reference / across
  const bgW = LOUPE / shareOfPicture
  const bgH = bgW * (p.height / p.width)
  const pos = (frac: number, size: number) => Math.min(0, Math.max(LOUPE - size, LOUPE / 2 - frac * size))
  return (
    <div
      className="loupe"
      aria-hidden="true"
      style={{ backgroundImage: `url(${dataUrl(p.img)})`, backgroundSize: `${bgW}px ${bgH}px`, backgroundPosition: `${pos(u, bgW)}px ${pos(v, bgH)}px` }}
    />
  )
}

function rowsFor(photo: SitePhoto, journey: Journey, p: SitePass): Row[] {
  const first = journey.passes[0]
  const rows: Row[] = []
  const enlarged = photo.width < 1080 // smaller than the app's size, so the app has to enlarge it

  if (p.pass === 0) {
    if (kb(p.bytes)) rows.push({ term: 'Size', state: 'plain', text: `${kb(p.bytes)}. This is the file as I brought it into the project.` })
  } else if (kb(p.bytes)) {
    rows.push({ term: 'Size', state: 'plain', text: kb(first?.bytes) ? `${kb(p.bytes)}. It started at ${kb(first.bytes)}.` : `${kb(p.bytes)}.` })
  }

  const kept = p.detail?.detail_kept
  if (p.pass > 0 && enlarged) {
    rows.push({ term: 'Fine detail', state: 'plain', text: 'Not measured for this one. The photograph is smaller than the app’s size, so the app enlarges it and there is nothing fair to compare with.' })
  } else if (p.pass > 0 && kept != null) {
    const share = Math.min(1, kept)
    rows.push({
      term: 'Fine detail',
      state: share >= 0.9 ? 'here' : share >= 0.5 ? 'going' : 'gone',
      text: share >= 0.995 ? 'About all of it is left.' : `${percent(share)} of the fine detail is left.`,
    })
  }

  const frame = p.detail?.frame_kept
  if (frame != null && frame < 0.995) {
    rows.push({ term: 'Frame', state: frame >= 0.9 ? 'here' : 'going', text: `${percent(frame)} of the picture is still in the frame. The edges were cropped away.` })
  }

  if (p.place) {
    const { rank, prob, top, place, lineup_size } = p.place
    rows.push(
      rank === 1
        ? { term: 'Place', state: 'here', text: `Given ${lineup_size} place names, a machine still puts ${shortPlace(place)} first, with ${percent(prob)} of its confidence.` }
        : { term: 'Place', state: 'gone', text: `Given ${lineup_size} place names, a machine now puts ${shortPlace(top)} first. ${shortPlace(place)} comes ${rank}${rank === 2 ? 'nd' : rank === 3 ? 'rd' : 'th'}.` },
    )
  }

  if (p.pass > 0) {
    const s = journey.settled_at
    rows.push(
      s != null && p.pass >= s
        ? { term: 'Change', state: 'plain', text: `It has stopped changing. From pass ${s} on, every pass gives back the same picture.` }
        : { term: 'Change', state: 'plain', text: p.pass >= journey.generations ? `Still changing after ${journey.generations} passes.` : 'Still changing with every pass.' },
    )
  }

  rows.push(
    p.pass === 0
      ? { term: 'Hidden details', state: 'gone', text: 'A phone saves the date, the camera and often the location inside a photo. Mine were already missing: the app I used to move my photographs here had removed them.' }
      : { term: 'Hidden details', state: 'gone', text: 'The date, the camera and the location a phone saves inside a photo are removed by the upload.' },
  )
  return rows
}

/** A sentence or two about this photograph, written from the numbers in the export. */
function foundFor(photo: SitePhoto): string[] {
  const out: string[] = []
  const j = (id: string) => photo.journeys[id]
  const lastDetail = (journey: Journey) => {
    const v = journey.series.detail_kept ?? []
    for (let i = v.length - 1; i > 0; i--) if (v[i] != null) return Math.min(1, v[i] as number)
    return null
  }
  const enlarged = photo.width < 1080
  const up = j('reupload')
  if (up) out.push(up.settled_at != null ? `Uploading it again and again stopped changing anything at pass ${up.settled_at}.` : `Uploading it again and again was still changing it at pass ${up.generations}.`)
  const shot = j('screenshot')
  if (shot) {
    const d = lastDetail(shot)
    const left = !enlarged && d != null ? ` By then ${percent(d)} of its fine detail was left.` : ''
    out.push(shot.settled_at != null ? `Screenshotting it on one phone stopped at pass ${shot.settled_at}.${left}` : `Screenshotting it on one phone was still changing it at pass ${shot.generations}.${left}`)
  }
  const phones = j('screenshot_many_phones')
  if (phones) {
    const d = lastDetail(phones)
    const left = !enlarged && d != null ? `, with ${percent(d)} of its fine detail left` : ''
    out.push(phones.settled_at != null ? `On a different phone every time it stopped at pass ${phones.settled_at}${left}.` : `On a different phone every time it never settled: it was still changing at pass ${phones.generations}${left}.`)
  }
  const loose = j('screenshot_loose_crop')
  if (loose) {
    const d = lastDetail(loose)
    const f = loose.series.frame_kept?.[loose.generations]
    if (!enlarged && d != null && f != null) out.push(`With a careless crop it lost the most: ${percent(d)} of its fine detail and ${percent(f)} of its frame were left after ${loose.generations} passes.`)
  }
  return out
}

export default function Story({ site }: { site: Site }) {
  const photos = useMemo(
    () => PHOTOS.map((meta) => ({ meta, photo: site.photos.find((p) => p.stem === meta.stem) })).filter((x): x is { meta: (typeof PHOTOS)[number]; photo: SitePhoto } => !!x.photo),
    [site],
  )
  const [stem, setStem] = useState(photos[0]?.photo.stem)
  const [journeyId, setJourneyId] = useState('screenshot_many_phones')
  const [index, setIndex] = useState(0)
  const [focus, setFocus] = useState<Focus>(() => ({ x: photos[0]?.meta.focus[0] ?? 0.5, y: photos[0]?.meta.focus[1] ?? 0.5 }))

  const current = photos.find((x) => x.photo.stem === stem) ?? photos[0]
  const journeys = JOURNEYS.filter((j) => current?.photo.journeys[j.id])
  const chosen = journeys.find((j) => j.id === journeyId) ?? journeys[0]
  const journey = current && chosen ? current.photo.journeys[chosen.id] : undefined
  const passes = journey?.passes ?? []
  const p = passes[Math.min(index, passes.length - 1)]
  const next = passes[index + 1]

  useEffect(() => {
    if (next) new Image().src = dataUrl(next.img) // have the next picture ready
  }, [next])

  if (!current || !chosen || !journey || !p) return <p className="faint">No photographs have been published yet.</p>
  const { photo, meta } = current
  const rows = rowsFor(photo, journey, p)
  const reference = passes[1]?.width ?? 1080
  const lines = journeys.map((j) => ({ id: j.id, values: (photo.journeys[j.id].series.detail_kept ?? []).map((v) => (v == null ? null : Math.min(1, v))) }))
  const found = foundFor(photo)
  const enlarged = photo.width < 1080

  function moveLoupe(e: React.MouseEvent<HTMLImageElement>) {
    const r = e.currentTarget.getBoundingClientRect()
    const u = (e.clientX - r.left) / r.width, v = (e.clientY - r.top) / r.height
    const [x0, y0, x1, y1] = p.detail?.box ?? [0, 0, photo.width, photo.height]
    setFocus({ x: (x0 + u * (x1 - x0)) / photo.width, y: (y0 + v * (y1 - y0)) / photo.height })
  }

  return (
    <>
      <section className="opening">
        <h1>I passed my photographs along, again and again, and kept every copy.</h1>
        <p className="lead">
          Every time a picture is sent, uploaded or screenshotted, something rewrites it. Choose what happens to the photograph,
          then pass it on and see what is left.
        </p>
      </section>

      <section aria-label="The photograph and its passes">
        <fieldset className="choice">
          <legend>What happens to it</legend>
          {journeys.map((j) => (
            <label key={j.id} className={j.id === chosen.id ? 'on' : ''}>
              <input type="radio" name="journey" checked={j.id === chosen.id} onChange={() => { setJourneyId(j.id); setIndex(0) }} />
              {j.label}
            </label>
          ))}
        </fieldset>
        <p className="muted says">{chosen.says}</p>

        <div className="player">
          <div>
            <div className="stage">
              <img
                key={p.img}
                src={dataUrl(p.img)}
                alt={`${meta.alt} ${p.pass === 0 ? 'The original.' : `After ${p.pass} ${p.pass === 1 ? 'pass' : 'passes'}.`}`}
                width={p.width ?? undefined}
                height={p.height ?? undefined}
                onClick={moveLoupe}
              />
              <span className="tag">{p.pass === 0 ? 'The original' : `Pass ${p.pass} of ${journey.generations}`}</span>
            </div>
            <div className="controls">
              <button className="primary" onClick={() => setIndex(next ? index + 1 : 0)}>{next ? 'Pass it on' : 'Start again'}</button>
              <div className="stops" role="group" aria-label="Go to a pass">
                {passes.map((s, i) => (
                  <button key={s.pass} className={i === index ? 'current' : ''} aria-current={i === index ? 'step' : undefined} onClick={() => setIndex(i)}>
                    {s.pass === 0 ? 'Original' : s.pass}
                  </button>
                ))}
              </div>
            </div>
            <p className="faint small">I kept all {journey.generations} passes. The page shows {passes.length - 1} of them.</p>
          </div>

          <div>
            <h2 className="left-title" aria-live="polite">{p.pass === 0 ? 'Before any pass' : `What is left after ${p.pass === 1 ? 'one pass' : `${p.pass} passes`}`}</h2>
            <dl className="left">
              {rows.map((r) => (
                <div key={r.term} className={`row ${r.state}`}>
                  <dt>
                    {r.term}
                    {r.state !== 'plain' && <span className="state">{STATE_WORD[r.state]}</span>}
                  </dt>
                  <dd>{r.text}</dd>
                </div>
              ))}
            </dl>
            <div className="closer">
              <Loupe p={p} photo={photo} focus={focus} reference={reference} />
              <p className="small muted">Look closer. This is the same spot at every pass. Click the photograph to look somewhere else.</p>
            </div>
          </div>
        </div>
      </section>

      <section aria-label="Choose a photograph">
        <h2>Six photographs of mine</h2>
        <div className="picker">
          {photos.map(({ photo: ph, meta: m }) => (
            <button key={ph.stem} className={ph.stem === photo.stem ? 'current' : ''} aria-pressed={ph.stem === photo.stem} onClick={() => { setStem(ph.stem); setIndex(0); setFocus({ x: m.focus[0], y: m.focus[1] }) }}>
              <img src={dataUrl(ph.thumb)} alt={m.alt} loading="lazy" />
              <span>{m.name}</span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2>What happened to this one</h2>
        {found.map((s) => <p key={s}>{s}</p>)}
        {enlarged ? (
          <p className="muted">This photograph is only {photo.width} pixels wide, smaller than the app’s size. The app enlarges it, so its fine detail cannot be compared fairly and it has no line below.</p>
        ) : (
          <>
            <h3>Fine detail left, pass by pass</h3>
            <DetailLine lines={lines} selected={chosen.id} current={p.pass} label={`Share of fine detail left in ${meta.name} over ${journey.generations} passes`} />
          </>
        )}
        <p>
          The same step repeated settles: after a few passes it hands back the picture it was given. The damage only keeps adding up
          when something changes from one pass to the next, such as a different phone or a different crop. That is closer to how a
          picture really travels.
        </p>
        <p className="muted">
          <Link to="/how">How each of these is measured, and what the measurements cannot show</Link>
        </p>
      </section>

      <section>
        <h2>Try it with your own photo</h2>
        <TryYourOwn />
      </section>

      <section>
        <h2>What comes next</h2>
        <p>
          So far no AI has touched these pictures. The next loop is the one the project is named after: a machine looks at the
          photograph and describes it in words, a second machine draws a new picture from those words alone, and the result goes
          round again. I expect it to keep what is typical (a street, a mountain, a person) and to drop what is specific (this
          street, these words on a sign, me). That loop has not been run yet, so there is nothing of it on this page.
        </p>
        <p className="muted">
          <Link to="/about">Why I am doing this</Link>
        </p>
      </section>
    </>
  )
}
