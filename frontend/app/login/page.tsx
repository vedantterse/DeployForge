import AuthForm from "@/components/AuthForm";

export const metadata = { title: "Log in · DeployForge" };

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
