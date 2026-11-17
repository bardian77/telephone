import { useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { loadIndex, type Index } from '../data'
import ChainPage from './ChainPage'
import Compare from './Compare'
import ExperimentPage from './ExperimentPage'
import Home from './Home'
import Label from './Label'
import Photo from './Photo'

/** The technical pages: every chain and every measurement, read from `telephone export`.
 * They are kept for my own work and are not part of the first page. */
export default function Lab() {
  const [index, setIndex] = useState<Index | null>(null)
  const [sample, setSample] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    loadIndex()
      .then(({ index, sample }) => { setIndex(index); setSample(sample) })
      .catch((e) => setErr(String(e)))
  }, [])
  if (err) return <p className="error">{err}</p>
  if (!index) return <p className="faint">Loading…</p>
  return (
    <>
      {sample && (
        <div className="banner">
          This is a <b>simulation</b>: made-up test pictures put through stand-in models, so these pages work before a real
          run has been exported. None of it is a result.
        </div>
      )}
      <Routes>
        <Route index element={<Home index={index} />} />
        <Route path="photo/:image" element={<Photo index={index} />} />
        <Route path="experiments/:id" element={<ExperimentPage index={index} />} />
        <Route path="chain/:key" element={<ChainPage index={index} />} />
        <Route path="compare" element={<Compare index={index} />} />
        <Route path="label" element={<Label index={index} />} />
      </Routes>
    </>
  )
}
