import { AppShell } from "@/components/AppShell";
import { getCurrentUser } from "@/lib/app-data";

export const dynamic = "force-dynamic";

export default async function InkwellAppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  return <AppShell email={user?.email}>{children}</AppShell>;
}
