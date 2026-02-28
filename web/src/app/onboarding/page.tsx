"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSaveConfig } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { toast } from "sonner";

const LLM_PARTNERS = [
  { id: "openai", label: "OpenAI" },
  { id: "anthropic", label: "Anthropic" },
  { id: "google", label: "Google Gemini" },
  { id: "mistral", label: "Mistral" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const saveConfig = useSaveConfig();

  const [step, setStep] = useState(0);
  const [llmPartner, setLlmPartner] = useState("");
  const [githubToken, setGithubToken] = useState("");

  const handleSave = () => {
    if (!llmPartner) {
      toast.error("Please select an LLM partner.");
      return;
    }
    if (!githubToken.trim()) {
      toast.error("Please enter a GitHub token.");
      return;
    }

    saveConfig.mutate(
      { llm_partner: llmPartner, github_token: githubToken },
      {
        onSuccess: () => {
          toast.success("Configuration saved!");
          router.push("/");
        },
        onError: () => {
          toast.error("Failed to save configuration. Please try again.");
        },
      }
    );
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle className="text-2xl">Welcome to ForgeStream</CardTitle>
          <CardDescription>
            {step === 0
              ? "Step 1 of 2 — Choose your LLM partner"
              : "Step 2 of 2 — Enter your GitHub token"}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {step === 0 ? (
            <div className="grid gap-3" role="radiogroup" aria-label="LLM partner selection">
              {LLM_PARTNERS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="radio"
                  aria-checked={llmPartner === p.id}
                  onClick={() => setLlmPartner(p.id)}
                  className={`flex items-center gap-3 rounded-lg border p-4 text-left text-sm transition-colors ${
                    llmPartner === p.id
                      ? "border-primary bg-primary/5 font-medium"
                      : "border-input hover:bg-accent"
                  }`}
                >
                  <span
                    className={`h-3 w-3 rounded-full border ${
                      llmPartner === p.id
                        ? "border-primary bg-primary"
                        : "border-muted-foreground"
                    }`}
                  />
                  {p.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="github-token">GitHub Personal Access Token</Label>
                <Input
                  id="github-token"
                  type="password"
                  placeholder="ghp_xxxxxxxxxxxx"
                  value={githubToken}
                  onChange={(e) => setGithubToken(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  autoCapitalize="none"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                We don&apos;t store your token in the browser after saving.
              </p>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex justify-between">
          {step > 0 && (
            <Button variant="outline" onClick={() => setStep(0)}>
              Back
            </Button>
          )}
          <div className="ml-auto">
            {step === 0 ? (
              <Button
                onClick={() => {
                  if (!llmPartner) {
                    toast.error("Please select an LLM partner.");
                    return;
                  }
                  setStep(1);
                }}
              >
                Next
              </Button>
            ) : (
              <Button
                onClick={handleSave}
                disabled={saveConfig.isPending}
              >
                {saveConfig.isPending ? "Saving…" : "Save & Continue"}
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
