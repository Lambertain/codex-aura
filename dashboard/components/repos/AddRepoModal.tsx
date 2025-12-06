import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

export function AddRepoModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState("");
  const queryClient = useQueryClient();

  const addRepo = useMutation({
    mutationFn: (repoUrl: string) =>
      apiClient("/api/v1/repos", {
        method: "POST",
        body: JSON.stringify({ url: repoUrl }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repos"] });
      onClose();
      setUrl("");
    },
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Repository</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="repo-url">Repository URL</Label>
            <Input
              id="repo-url"
              placeholder="https://github.com/owner/repo"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <Button
            onClick={() => addRepo.mutate(url)}
            disabled={addRepo.isPending || !url}
            className="w-full"
          >
            {addRepo.isPending ? "Adding..." : "Add Repository"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}