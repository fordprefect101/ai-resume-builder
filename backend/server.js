import express from 'express';

const app = express();
const PORT = process.env.PORT || 8081;

app.get('/health', (_req, res) => {
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`API listening on http://localhost:${PORT}`);
});