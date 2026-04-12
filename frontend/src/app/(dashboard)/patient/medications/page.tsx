import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function MedicationsIndex() {
  const session = await auth();
  
  if (!session?.user?.id) {
    redirect("/login");
  }
  
  // The schedule page handles displaying patient medications natively
  redirect(`/patient/medications/${session.user.id}/schedule`);
}
