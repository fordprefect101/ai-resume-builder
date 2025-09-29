import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  build: {
    lib: {
      entry: {
        widget: resolve(__dirname, 'widget.js'),
        'widget-loader': resolve(__dirname, 'widget-loader.js'),
      },
      formats: ['es']
    },
    rollupOptions: {
      output: {
        dir: 'dist',
        entryFileNames: '[name].js',
      }
    },
    sourcemap: true,
    minify: true,
    target: 'es2020'
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './')
    }
  },
  server: {
    port: 4173,
    open: true,
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  }
});
