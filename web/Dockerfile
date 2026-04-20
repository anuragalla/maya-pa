FROM nginx:alpine

# The /usr/share/nginx/html directory is overridden at runtime via a
# bind mount to ./web/dist (built in CI and shipped in the release
# tarball). Keep the image minimal — no bun/vite in prod.
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
