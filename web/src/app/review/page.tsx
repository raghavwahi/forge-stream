"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useCreateRepo, type ProposedItem, type CreationProgress } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { toast } from "sonner";
import { Sparkles, Trash2, ArrowLeft } from "lucide-react";

function readSessionItems(): ProposedItem[] {
  if (typeof window === "undefined") return [];
  const raw = sessionStorage.getItem("forgestream_items");
  if (!raw) return [];
  try {
    return JSON.parse(raw) as ProposedItem[];
  } catch {
    sessionStorage.removeItem("forgestream_items");
    return [];
  }
}

export default function ReviewPage() {
  const router = useRouter();
  const createRepo = useCreateRepo();

  const [items, setItems] = useState<ProposedItem[]>(() => readSessionItems());
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(readSessionItems().map((i) => i.id))
  );
  const [progress, setProgress] = useState<CreationProgress | null>(null);

  const toggleItem = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(items.map((i) => i.id)));
    }
  };

  const handleDelete = (id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const handleEnhance = useCallback(
    (id: string) => {
      toast.info(`Enhancing item: ${items.find((i) => i.id === id)?.title}`);
      // In a full implementation this would call an API to expand/improve the item
    },
    [items]
  );

  const handleCreate = () => {
    const selectedItems = items.filter((i) => selected.has(i.id));
    if (selectedItems.length === 0) {
      toast.error("Select at least one item to create.");
      return;
    }

    setProgress({ step: "Initializing…", progress: 0, done: false });

    createRepo.mutate(
      { items: selectedItems },
      {
        onSuccess: (data) => {
          setProgress({
            step: "Complete!",
            progress: 100,
            done: true,
            repo_url: data.repo_url,
          });
          toast.success("Repository created successfully!");
        },
        onError: () => {
          setProgress({
            step: "Failed",
            progress: 0,
            done: true,
            error: "Creation failed. Please try again.",
          });
          toast.error("Repository creation failed.");
        },
      }
    );
  };

  if (progress) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>
              {progress.error
                ? "Creation Failed"
                : progress.done
                  ? "🎉 Repository Created!"
                  : "Creating Repository…"}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <Progress value={progress.progress} />
            <p className="text-sm text-muted-foreground">{progress.step}</p>
            {progress.repo_url && (
              <a
                href={progress.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-primary underline"
              >
                Open repository →
              </a>
            )}
            {progress.error && (
              <p className="text-sm text-destructive">{progress.error}</p>
            )}
          </CardContent>
          {progress.done && (
            <CardFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setProgress(null);
                  if (!progress.error) router.push("/");
                }}
              >
                {progress.error ? "Try Again" : "Back to Dashboard"}
              </Button>
            </CardFooter>
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen justify-center bg-background p-4">
      <div className="w-full max-w-3xl py-10">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Back to dashboard"
              onClick={() => router.push("/")}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold">Review Proposed Items</h1>
              <p className="text-sm text-muted-foreground">
                {selected.size} of {items.length} selected
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={toggleAll}>
              {selected.size === items.length ? "Deselect All" : "Select All"}
            </Button>
          </div>
        </div>

        <div className="grid gap-3">
          {items.map((item) => (
            <Card
              key={item.id}
              className={`transition-colors ${
                selected.has(item.id) ? "border-primary/40" : "opacity-60"
              }`}
            >
              <CardContent className="flex items-start gap-4 p-4">
                <Checkbox
                  checked={selected.has(item.id)}
                  onChange={() => toggleItem(item.id)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{item.title}</span>
                    <Badge variant="secondary">{item.type}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {item.description}
                  </p>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleEnhance(item.id)}
                    aria-label={`Enhance ${item.title}`}
                  >
                    <Sparkles className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(item.id)}
                    aria-label={`Delete ${item.title}`}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}

          {items.length === 0 && (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No items to review. Go back and generate a new plan.
              </CardContent>
            </Card>
          )}
        </div>

        {items.length > 0 && (
          <div className="mt-6 flex justify-end">
            <Button onClick={handleCreate} disabled={createRepo.isPending}>
              {createRepo.isPending ? "Creating…" : "Create Repository"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
