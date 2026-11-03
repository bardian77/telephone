import { useEffect, useState } from 'react'
import { HashRouter, NavLink, Route, Routes } from 'react-router-dom'
import { loadIndex, type Index } from './data'
import Home from './pages/Home'
import Photo from './pages/Photo'
import ExperimentPage from './pages/ExperimentPage'
import ChainPage from './pages/ChainPage'
import Compare from './pages/Compare'
import Label from './pages/Label'
import Live from './pages/Live'
import About from './pages/About'

export default function App() {
  const [index, setIndex] = useState<Index | null>(null)
  const [sample, setSample] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { loadIndex().then(({ index, sample }) => { setIndex(index); setSample(sample) }).catch((e) => setErr(String(e))) }, [])
  return (
    <HashRouter>
      <div className="shell">
        <header className="top">
          <NavLink to="/" className="brand">Telephone</NavLink>
          <nav>
            <NavLink to="/" end>Chains</NavLink>
            <NavLink to="/compare">Compare</NavLink>
            <NavLink to="/live">Live</NavLink>
            <NavLink to="/label">Label</NavLink>
            <NavLink to="/about">About</NavLink>
            <a href="https://github.com/bardian77/telephone">Code</a>
          </nav>
        </header>
        {sample && <div className="banner">Showing the <b>sample dataset</b>: synthetic test images through mock models, so the site works before any real experiment has run. Real chains replace this after <code>telephone export</code>.</div>}
        {err && <p style={{ color: 'var(--dead)' }}>{err}</p>}
        {index ? (
          <Routes>
            <Route path="/" element={<Home index={index} />} />
            <Route path="/photo/:image" element={<Photo index={index} />} />
            <Route path="/experiments/:id" element={<ExperimentPage index={index} />} />
            <Route path="/chain/:key" element={<ChainPage index={index} />} />
            <Route path="/compare" element={<Compare index={index} />} />
            <Route path="/label" element={<Label index={index} />} />
            <Route path="/live" element={<Live index={index} />} />
            <Route path="/about" element={<About />} />
          </Routes>
        ) : !err && <p className="faint">Loading…</p>}
        <footer>Bardia Nasab · 5IMAG022W The Networked Photograph · {index ? `data exported ${new Date(index.generated_at).toLocaleDateString()}` : ''}</footer>
      </div>
    </HashRouter>
  )
}
