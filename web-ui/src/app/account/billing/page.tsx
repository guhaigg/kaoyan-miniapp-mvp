import { redirect } from "next/navigation";

export default function AccountBillingPage() {
  redirect("/account?tab=account&panel=billing");
}
