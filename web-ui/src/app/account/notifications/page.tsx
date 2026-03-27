import { redirect } from "next/navigation";

export default function AccountNotificationsPage() {
  redirect("/account?tab=activity&panel=notifications");
}
