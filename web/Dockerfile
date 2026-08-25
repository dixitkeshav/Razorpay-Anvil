FROM node:20-slim AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

FROM node:20-slim

WORKDIR /app

# Carry the build stage's already-correct node_modules forward instead of
# reinstalling a subset in this stage -- a first attempt at a selective
# `npm install --omit=dev vite @vitejs/plugin-react` here silently ended
# up missing, and `vite preview`'s config loader fell back to npx
# auto-installing an unpinned, incompatible major version of vite at
# container start. Copying the whole directory is simpler and has no such
# failure mode. See docs/JOURNAL.md.
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/package.json ./
COPY --from=build /app/vite.config.ts ./

EXPOSE 5173

CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
