import type { Config } from 'tailwindcss';
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: { extend: { colors: { ink: '#14202b', paper: '#f6f4ef', amber: '#d99a2b', mist: '#e8e5dd' } } },
  plugins: []
};
export default config;
