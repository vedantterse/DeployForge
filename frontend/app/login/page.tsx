import Link from "next/link";
import AuthForm from "@/components/AuthForm";
import { ForgeIcon } from "@/components/Icons";

export default function LoginPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 p-8">
      <Link
        href="/"
        className="flex items-center gap-2 font-semibold tracking-tight"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
          <ForgeIcon className="h-5 w-5" />
        </span>
        DeployForge
      </Link>
      <AuthForm mode="login" />
    </main>
  );
}
