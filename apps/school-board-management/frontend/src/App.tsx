import { Outlet, Link, NavLink } from 'react-router-dom'
import { keycloak } from './keycloak'

export default function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="border-b">
        <div className="mx-auto max-w-5xl px-4 py-3 flex items-center justify-between">
          <Link to="/" className="font-semibold">OSSS</Link>
          <nav className="flex gap-4">
            <NavLink to="/meetings" className={({isActive})=> isActive? 'font-semibold' : ''}>Meetings</NavLink>
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
