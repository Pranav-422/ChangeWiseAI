export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: unknown[] = [],
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function describe(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}
