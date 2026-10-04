import './globals.css';

export const metadata = {
  title: 'DocuSleuth — Evidence before eloquence',
  description: 'A private evidence desk for answers that can show their work.'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><head><meta httpEquiv="Content-Security-Policy" content="default-src 'self'; base-uri 'self'; object-src 'none'; frame-src 'self' blob:; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' http://localhost:8000 https://api.openai.com; frame-ancestors https://*.manus.computer http://localhost:3000" /></head><body>{children}</body></html>;
}
