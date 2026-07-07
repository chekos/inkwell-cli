import { NextResponse } from "next/server";
import { ZodError } from "zod";

import { createImport } from "@/lib/imports";

export async function POST(request: Request) {
  try {
    const result = await createImport(await request.json());

    if (!result.ok) {
      return NextResponse.json({ error: result.error }, { status: result.status });
    }

    return NextResponse.json({
      jobId: result.jobId,
      statusUrl: result.statusUrl,
      dispatched: result.dispatched,
      dispatchReason: result.dispatchReason,
    });
  } catch (error) {
    if (error instanceof ZodError) {
      return NextResponse.json({ error: "Paste a valid URL." }, { status: 400 });
    }

    return NextResponse.json({ error: "Could not create the import." }, { status: 500 });
  }
}
