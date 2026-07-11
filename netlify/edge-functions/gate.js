// Gate all /s/* share pages behind a token stored in Netlify env vars.
// Token is passed as ?t=TOKEN in the URL.
export default async function (request, context) {
  const url = new URL(request.url);
  const raw = url.searchParams.get("t") || "";
  const token = raw.replace(/[^a-zA-Z0-9]/g, "");

  if (!token) {
    return Response.redirect(`${url.origin}/denied.html`, 302);
  }

  const gallery = Netlify.env.get("SHARE_" + token);
  if (!gallery) {
    return Response.redirect(`${url.origin}/denied.html`, 302);
  }

  return context.next();
}

export const config = { path: "/s/*" };
