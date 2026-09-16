// Client-side OCR via Tesseract.js — the image never leaves the browser,
// consistent with the "no data stored, nothing sent unnecessarily"
// principle applied everywhere else in this app. Good for a clean, well-lit
// photo of printed packaging text; noticeably weaker than a cloud vision API
// on glare/skew/low light. Extracted text is meant to be reviewed/edited by
// the user before analysis, never auto-submitted — OCR mistakes on a
// medication name are exactly the kind of error this app can't silently eat.

import { createWorker } from "tesseract.js";

export class OcrError extends Error {}

export async function extractTextFromImage(file: File): Promise<string> {
  let worker;
  try {
    worker = await createWorker("eng");
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new OcrError(`Couldn't start the text reader: ${message}`);
  }

  try {
    const { data } = await worker.recognize(file);
    return data.text.trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new OcrError(`Couldn't read text from that image: ${message}`);
  } finally {
    await worker.terminate();
  }
}
