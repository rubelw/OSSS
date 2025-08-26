import type { NextApiRequest, NextApiResponse } from 'next'
import { getToken } from 'next-auth/jwt'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const jwt = await getToken({ req, secret: process.env.NEXTAUTH_SECRET })
  const issuer = process.env.KEYCLOAK_ISSUER!
  const clientId = process.env.KEYCLOAK_CLIENT_ID!
  const post = process.env.POST_LOGOUT_REDIRECT_URI ?? process.env.NEXTAUTH_URL ?? '/'

  const url = new URL(`${issuer}/protocol/openid-connect/logout`)
  if (jwt?.id_token) url.searchParams.set('id_token_hint', String(jwt.id_token))
  url.searchParams.set('client_id', clientId)
  url.searchParams.set('post_logout_redirect_uri', post)

  res.redirect(url.toString())
}
