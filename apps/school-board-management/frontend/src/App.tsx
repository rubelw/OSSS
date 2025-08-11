import { Outlet, Link, NavLink, useMatch } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { keycloak } from './keycloak'

function PlanningMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const isActive = !!useMatch('/planning/*') || !!useMatch('/planning')

  // close on click outside / escape
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`inline-flex items-center gap-1 ${isActive ? 'font-semibold' : ''}`}
      >
        Planning
        <span className="i-chevron w-3 h-3">{/* tiny caret */}</span>
      </button>

      <div
        role="menu"
        className={`absolute right-0 z-20 mt-2 w-48 rounded-xl border bg-white shadow-lg ${open ? 'block' : 'hidden'}`}
      >
        <NavLink
          to="/planning"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
          end
        >
          Overview
        </NavLink>
        <NavLink
          to="/planning/strategic_plans"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Strategic Plans
        </NavLink>
        <NavLink
          to="/planning/goals"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Goals
        </NavLink>
        <NavLink
          to="/planning/scorecards"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Scorecards
        </NavLink>
        <NavLink
          to="/planning/progress_tracking"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Progress Tracking
        </NavLink>
      </div>
    </div>
  )
}

function MeetingsMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const isActive = !!useMatch('/meetings/*') || !!useMatch('/meetings')

  // close on click outside / escape
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`inline-flex items-center gap-1 ${isActive ? 'font-semibold' : ''}`}
      >
        Meetings
        <span className="i-chevron w-3 h-3">{/* tiny caret */}</span>
      </button>

      <div
        role="menu"
        className={`absolute right-0 z-20 mt-2 w-48 rounded-xl border bg-white shadow-lg ${open ? 'block' : 'hidden'}`}
      >
        <NavLink
          to="/meetings"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
          end
        >
          Overview
        </NavLink>
        <NavLink
          to="/meetings/agenda_minutes"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Agenda/Minutes
        </NavLink>
        <NavLink
          to="/meetings/packets"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Packets
        </NavLink>
        <NavLink
          to="/meetings/voting"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Voting
        </NavLink>
        <NavLink
          to="/meetings/paperless_meetings"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Paperless Meetings
        </NavLink>
      </div>
    </div>
  )
}

function EvaluationMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const isActive = !!useMatch('/evaluation/*') || !!useMatch('/evaluation')

  // close on click outside / escape
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`inline-flex items-center gap-1 ${isActive ? 'font-semibold' : ''}`}
      >
        Evaluations
        <span className="i-chevron w-3 h-3">{/* tiny caret */}</span>
      </button>

      <div
        role="menu"
        className={`absolute right-0 z-20 mt-2 w-48 rounded-xl border bg-white shadow-lg ${open ? 'block' : 'hidden'}`}
      >
        <NavLink
          to="/evaluation"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
          end
        >
          Overview
        </NavLink>
        <NavLink
          to="/evaluation/evaluations"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Evaluations
        </NavLink>
        <NavLink
          to="/evaluation/surveys"
          className={({ isActive }) =>
            'block px-3 py-2 hover:bg-gray-50 ' + (isActive ? 'font-semibold' : '')
          }
          onClick={() => setOpen(false)}
        >
          Surveys
        </NavLink>
      </div>
    </div>
  )
}


export default function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="border-b">
        <div className="mx-auto max-w-5xl px-4 py-3 flex items-center justify-between">
          <Link to="/" className="font-semibold">OSSS</Link>
          <nav className="flex gap-4">
            <NavLink to="/communications" className={({isActive})=> isActive? 'font-semibold' : ''}>Communications</NavLink>
            <NavLink to="/document" className={({isActive})=> isActive? 'font-semibold' : ''}>Documents</NavLink>
            <EvaluationMenu />
            <PlanningMenu />
            <MeetingsMenu />
            <NavLink to="/policies" className={({isActive})=> isActive? 'font-semibold' : ''}>Policies</NavLink>
          </nav>
          <div className="text-sm">
            <button onClick={() => keycloak.login({ redirectUri: window.location.href })} className="mr-3">Login</button>
            <button onClick={() => keycloak.logout({ redirectUri: window.location.origin })}>Logout</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
