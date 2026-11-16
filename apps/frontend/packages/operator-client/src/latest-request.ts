export interface LatestRequestHandle {
  signal: AbortSignal;
  isCurrent(): boolean;
}

/** Cancels an older read and rejects its result after the caller's scope changes. */
export class LatestRequest {
  #generation = 0;
  #controller: AbortController | null = null;

  begin(): LatestRequestHandle {
    this.#controller?.abort();
    const controller = new AbortController();
    const generation = ++this.#generation;
    this.#controller = controller;

    return {
      signal: controller.signal,
      isCurrent: () => generation === this.#generation && !controller.signal.aborted,
    };
  }

  cancel(): void {
    this.#generation += 1;
    this.#controller?.abort();
    this.#controller = null;
  }
}
