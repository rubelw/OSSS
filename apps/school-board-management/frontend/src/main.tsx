import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import App from './App'
import Home from './pages/Home'
import MeetingsList from './pages/MeetingsList'
import MeetingDetail from './pages/MeetingDetail'
import PoliciesList from './pages/PoliciesList'
import PolicyDetail from './pages/PolicyDetail'
import { keycloak } from './keycloak'

const router = createBrowserRouter([
  { path: '/', element: <App />, children: [
    { index: true, element: <Home /> },
    { path: 'meetings', element: <MeetingsList /> },
    { path: 'meetings/:id', element: <MeetingDetail /> },
    { path: 'policies', element: <PoliciesList /> },
    { path: 'policies/:id', element: <PolicyDetail /> },
  ]}
])

async function bootstrap(){
  try {
    await keycloak.init({ onLoad: "check-sso", pkceMethod: "S256" });
  } catch (e) {
    console.error('Keycloak init failed', e);
  } finally {
    ReactDOM.createRoot(document.getElementById('root')!).render(
      <React.StrictMode>
        <RouterProvider router={router} />
      </React.StrictMode>
    )
  }
}
bootstrap()
