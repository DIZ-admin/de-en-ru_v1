/**
 * Lightweight Server-Sent Events decoder that preserves partial lines between chunks
 * and extracts payloads from `data:` lines.
 */
export class SSEDecoder {
  private buffer = "";

  /**
   * Push decoded text chunk into the buffer and return completed data payloads.
   * @param chunk Portion of SSE stream decoded to string
   * @param options Optional flags (e.g. final flush)
   */
  push(chunk: string, options: { isFinal?: boolean } = {}): string[] {
    const { isFinal = false } = options;
    const payloads: string[] = [];
    this.buffer += chunk;

    let newlineIndex = this.buffer.indexOf("\n");
    while (newlineIndex !== -1) {
      let line = this.buffer.slice(0, newlineIndex);
      this.buffer = this.buffer.slice(newlineIndex + 1);

      if (line.endsWith("\r")) {
        line = line.slice(0, -1);
      }

      if (line.length === 0) {
        newlineIndex = this.buffer.indexOf("\n");
        continue;
      }

      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data !== "{}" && data !== "") {
          payloads.push(data);
        }
      }

      newlineIndex = this.buffer.indexOf("\n");
    }

    if (isFinal && this.buffer.length > 0) {
      const remaining = this.buffer;
      this.buffer = "";
      if (remaining.startsWith("data: ")) {
        const data = remaining.slice(6);
        if (data !== "{}" && data !== "") {
          payloads.push(data);
        }
      }
    }

    return payloads;
  }
}
