import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function MedicationsIndex() {
  const session = await auth();
  
  if (!session?.user?.id) {
    redirect("/login");
  }
  
  redirect("/patient/medications/interactions");
}
