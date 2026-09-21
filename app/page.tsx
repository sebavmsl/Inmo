import { redirect } from "next/navigation";
import { getSessionProfile } from "@/lib/auth/session";

export default async function RootPage() {
  const perfil = await getSessionProfile();
  redirect(perfil ? "/dashboard" : "/login");
}
