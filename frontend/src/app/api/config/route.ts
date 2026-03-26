import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    clientId: process.env.AZURE_CLIENT_ID || "",
    tenantId: process.env.AZURE_TENANT_ID || "common",
  });
}
