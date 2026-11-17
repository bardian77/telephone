import { useEffect, useState } from 'react'
import { HashRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import About from './pages/About'
import HowItWorks from './pages/HowItWorks'
import Lab from './pages/Lab'
import Story from './pages/Story'
import { loadSite, type Site } from './site'

/** Start each page at its top, as a normal link would. */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0) // in braces: an effect must not return what scrollTo returns
  }, [pathname])
  return null
}

export default function App() {
  const [site, setSite] = useState<Site | null | undefined>(undefined) // undefined: still loading
  useEffect(() => { loadSite().then(setSite) }, [])
  const missing = (
    <p className="muted">
      The photographs have not been published to this copy of the site yet. They are written by <code>telephone export-site</code>.
    </p>
  )
  return (
    <HashRouter>
      <ScrollToTop />
      <a className="skip" href="#main">Skip to the page</a>
      <div className="shell">
        <header className="top">
          <NavLink to="/" className="brand" translate="no">Telephone</NavLink>
          <nav aria-label="Pages">
            <NavLink to="/" end>The photographs</NavLink>
            <NavLink to="/how">How it works</NavLink>
            <NavLink to="/about">About</NavLink>
          </nav>
        </header>
        <main id="main">
          {site === undefined ? (
            <p className="faint">Loading…</p>
          ) : (
            <Routes>
              <Route path="/" element={site ? <Story site={site} /> : missing} />
              <Route path="/how" element={<HowItWorks site={site} />} />
              <Route path="/about" element={<About />} />
              <Route path="/lab/*" element={<Lab />} />
            </Routes>
          )}
        </main>
        <footer>
          Bardia Nasab · 5IMAG022W The Networked Photograph ·{' '}
          <a href="https://github.com/bardian77/telephone">the code and every result</a>
          {site ? ` · pictures published ${new Intl.DateTimeFormat(undefined, { dateStyle: 'long' }).format(new Date(site.generated_at))}` : ''}
        </footer>
      </div>
    </HashRouter>
  )
}
