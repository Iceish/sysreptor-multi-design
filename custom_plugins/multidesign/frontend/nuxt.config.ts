import { fileURLToPath } from 'node:url';

export default defineNuxtConfig({
  extends: ['@sysreptor/plugin-base-layer'],
  srcDir: '.',
  appConfig: { pluginId: 'd42d1b7f-9c3b-4a62-a3f9-2d070d560127' },
  alias: { pinia: fileURLToPath(new URL('./node_modules/pinia', import.meta.url)) },
  typescript: { tsConfig: { compilerOptions: { types: ['node'] } } },
  nitro: { output: { publicDir: '../static/' } },
});
