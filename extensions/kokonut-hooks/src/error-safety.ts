/** Return a bounded exception class label without exposing its message. */
export function errorClass(error: unknown): string {
  if (!(error instanceof Error)) return 'NonError';

  try {
    const name = error.name;
    return typeof name === 'string' && /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(name)
      ? name
      : 'Error';
  } catch {
    return 'Error';
  }
}
