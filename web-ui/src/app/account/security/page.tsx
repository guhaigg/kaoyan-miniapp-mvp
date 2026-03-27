import { redirect } from "next/navigation";

export default function AccountSecurityPage() {
  redirect("/account?tab=account&panel=security");
}
