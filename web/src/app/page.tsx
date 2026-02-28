"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useGenerate } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { toast } from "sonner";
import { Search } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const generate = useGenerate();
  const [prompt, setPrompt] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) {
      toast.error("Please enter a prompt.");
      return;
    }

    generate.mutate(
      { prompt },
      {
        onSuccess: (data) => {
          // Store generated items in session storage so review page can read them
          sessionStorage.setItem(
            "forgestream_items",
            JSON.stringify(data.items)
          );
          router.push("/review");
        },
        onError: () => {
          toast.error("Generation failed. Please try again.");
        },
      }
    );
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-2xl">
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-3xl font-bold">ForgeStream</CardTitle>
            <CardDescription className="text-base">
              Describe what you want to build and we&apos;ll generate a plan for
              you.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="e.g. A REST API with auth, Postgres, and Docker…"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={generate.isPending}
                />
              </div>
              <Button type="submit" disabled={generate.isPending}>
                {generate.isPending ? "Generating…" : "Generate"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
