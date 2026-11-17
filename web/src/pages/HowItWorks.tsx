import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { JOURNEYS, PHOTOS, dataUrl, percent, shortPlace, type Journey, type Site } from '../site'

function lastOf(values: Array<number | null> | undefined): number | null {
  if (!values) return null
  for (let i = values.length - 1; i > 0; i--) if (values[i] != null) return values[i]
  return null
}

function placeAtEnd(j: Journey): string {
  const p = j.passes[j.passes.length - 1]?.place
  if (!p) return 'not measured'
  return p.rank === 1 ? `1st of ${p.lineup_size} (${percent(p.prob)})` : `${p.rank} of ${p.lineup_size}; first: ${shortPlace(p.top)}`
}

export default function HowItWorks({ site }: { site: Site | null }) {
  const [lab, setLab] = useState(false)
  useEffect(() => {
    // the lab pages are only offered when a real export of them is present
    fetch(dataUrl('index.json'))
      .then((r) => setLab(r.ok && (r.headers.get('content-type') ?? '').includes('json')))
      .catch(() => setLab(false))
  }, [])

  return (
    <article className="reading">
      <h1>How it works</h1>
      <p className="lead">
        A photograph goes round a loop. Each trip round is one pass. After every pass the result is saved and measured, and it
        becomes the starting point for the next pass.
      </p>

      <h2>The steps a pass can be made of</h2>
      <dl className="terms">
        <dt>Upload</dt>
        <dd>
          What a photo app does when you post a picture: it shrinks it to the app’s largest size (here 1080 pixels on the long
          side), saves it again as a JPEG at the app’s quality (here 72 out of 100), and removes the hidden details a camera
          stores in the file. This is a stand-in I wrote, with settings close to Instagram’s. It is not Instagram’s own code.
        </dd>
        <dt>Screenshot</dt>
        <dd>
          A phone shows the picture as large as fits on its screen, and the screen is captured. The picture is redrawn on the
          screen’s grid of pixels, so it is resized before the next upload. In one journey the crop is a few pixels off each
          time; in another the phone is a different size every pass.
        </dd>
        <dt>Describe, then redraw</dt>
        <dd>
          A machine writes a description of the picture, and a second machine draws a new picture from the description alone.
          This is the loop the project is named after. It has not been run yet.
        </dd>
      </dl>

      <h2>What is measured after each pass</h2>
      <dl className="terms">
        <dt>Size</dt>
        <dd>The size of the saved file.</dd>
        <dt>Fine detail</dt>
        <dd>
          How much pixel-to-pixel variation the picture has, as a share of what the same part of the original has when it is
          resized once to the same size. In the results files this is <code translate="no">detail_kept</code>, and it is read next to{' '}
          <code translate="no">ssim_native</code>, a standard similarity score made at the picture’s own size. What it cannot show: JPEG saving
          leaves faint square blocks, and those count as detail, so the number can flatter a heavily compressed picture.
        </dd>
        <dt>Frame</dt>
        <dd>How much of the original picture’s area is still inside the frame. Only the careless-crop journey loses any.</dd>
        <dt>Place</dt>
        <dd>
          For each photograph I wrote a list of 12 place names that includes the true one, before measuring anything. A vision
          model (CLIP) scores how well each name matches the picture. I report where the true name comes in that list and how
          much of the model’s confidence it gets. What it cannot show: this is one model and one list. Coming first in the list
          does not mean the machine knows the place. One check failed, and I have kept it: a close-up of rippled water, which I
          expected the model not to place, came first in its list anyway.
        </dd>
        <dt>Change</dt>
        <dd>
          Whether a pass still alters the picture. A journey counts as settled from the pass after which every pass hands
          back what it was given (in the files: <code translate="no">ssim_to_prev</code> of 1.000000 for at least three
          passes, to the end of the run). One pass that happens to change nothing does not count.
        </dd>
      </dl>

      {site && (
        <>
          <h2>The numbers after {Math.max(...site.photos.flatMap((p) => Object.values(p.journeys).map((j) => j.generations)))} passes</h2>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Photograph</th>
                  <th>Journey</th>
                  <th>Settled at pass</th>
                  <th className="num">Fine detail left</th>
                  <th className="num">Frame left</th>
                  <th>True place in its list</th>
                </tr>
              </thead>
              <tbody>
                {PHOTOS.flatMap((meta) => {
                  const photo = site.photos.find((p) => p.stem === meta.stem)
                  if (!photo) return []
                  const enlarged = photo.width < 1080
                  return JOURNEYS.filter((j) => photo.journeys[j.id]).map((j, i) => {
                    const journey = photo.journeys[j.id]
                    const detail = lastOf(journey.series.detail_kept)
                    return (
                      <tr key={`${meta.stem}-${j.id}`}>
                        <td>{i === 0 ? meta.name : ''}</td>
                        <td>{j.label}</td>
                        <td>{journey.settled_at ?? 'never'}</td>
                        <td className="num">{enlarged ? 'not comparable' : (percent(detail == null ? null : Math.min(1, detail)) ?? 'not measured')}</td>
                        <td className="num">{percent(lastOf(journey.series.frame_kept)) ?? 'not measured'}</td>
                        <td>{placeAtEnd(journey)}</td>
                      </tr>
                    )
                  })
                })}
              </tbody>
            </table>
          </div>
          <p className="small muted">
            The reflection photograph is only 460 pixels wide. The app enlarges it, so its fine detail has nothing fair to be
            compared with.
            {site.made_with.clip_model ? ` Place was scored with ${site.made_with.clip_model}` : ''}
            {site.made_with.preprocessing ? `, which looks at the ${site.made_with.preprocessing} of each picture.` : site.made_with.clip_model ? '.' : ''}
          </p>
        </>
      )}

      <h2>What went wrong on the way</h2>
      <ul>
        <li>
          I expected re-uploading to wear a photograph down a little more each time. It does not. Almost all of the change
          happens on the first upload, and then the loop hands back the same picture.
        </li>
        <li>
          I then expected screenshots to keep the damage adding up, because each one redraws the picture. With an exact crop
          on one phone, that loop settles as well. It only keeps going when something varies between passes.
        </li>
        <li>
          My first similarity score compared copies shrunk to 512 pixels wide. It reported almost no change in pictures that
          had plainly lost fine detail at full size. The fine-detail measure above replaced it.
        </li>
        <li>
          For the careless-crop journey, my first numbers mostly measured the cropping, not the damage. The comparison now
          follows the crop and compares each pass with the same part of the original.
        </li>
        <li>
          The vision model was being built with the wrong setting for its weights, and the software only warned about it. Every
          place score and every model-based distance was measured again after the fix.
        </li>
      </ul>

      <h2>Run it yourself</h2>
      <p>
        Everything is in <a href="https://github.com/bardian77/telephone">the repository</a>: the code, the six photographs, the
        list of place names, and one row of results for every pass of every journey. None of it needs a paid service.
      </p>
      {lab && (
        <p>
          <Link to="/lab">The lab</Link> shows every chain with all of its measurements.
        </p>
      )}
    </article>
  )
}
