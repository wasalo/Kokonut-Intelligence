/**
 * Directus companion route for the standalone field collector.
 *
 * Caddy owns the static file, so this endpoint redirects users who are
 * already inside Directus to the canonical companion-tool URL.
 */
export default {
  id: "kokonut-field-collector",
  handler: (router) => {
    router.get("/", (_req, res) => {
      res.redirect(302, "/field/field-collector.html");
    });
  },
};
