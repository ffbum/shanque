import { defineConfig } from '@umijs/max';

export default defineConfig({
  title: '山雀企业项目工作台',
  favicons: ['/static/mark.svg?v=shanque-2'],
  hash: true,
  publicPath: '/assets/',
  routes: [{ path: '/*', component: './Workbench', layout: false }],
  antd: {},
  model: false,
  initialState: false,
  access: false,
  request: {},
  mock: false,
  npmClient: 'npm',
  proxy: {
    '/api/page': {
      target: 'http://127.0.0.1:5086',
      changeOrigin: true,
      pathRewrite: { '^/api/page': '' },
    },
    '/api': { target: 'http://127.0.0.1:5086', changeOrigin: true },
  },
});
