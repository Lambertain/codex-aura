"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Key,
  Plus,
  Trash2,
  Copy,
  CheckCircle,
  AlertCircle,
  Code
} from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface ApiKey {
  id: string;
  name: string;
  key: string;
  created_at: string;
  last_used?: string;
  usage_count: number;
}

export default function ApiKeysPage() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [loading, setLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => {
    loadApiKeys();
  }, []);

  const loadApiKeys = async () => {
    try {
      const response = await fetch("/api/v1/api-keys");
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data.keys || []);
      }
    } catch (error) {
      console.error("Failed to load API keys:", error);
    }
  };

  const generateApiKey = async () => {
    if (!newKeyName.trim()) {
      toast({
        title: "Error",
        description: "Please enter a name for the API key",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/v1/api-keys", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: newKeyName.trim() }),
      });

      if (response.ok) {
        const data = await response.json();
        setApiKeys(prev => [data.key, ...prev]);
        setNewKeyName("");
        toast({
          title: "Success",
          description: "API key generated successfully",
        });
      } else {
        throw new Error("Failed to generate API key");
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate API key",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const revokeApiKey = async (keyId: string) => {
    if (!confirm("Are you sure you want to revoke this API key? This action cannot be undone.")) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/api-keys/${keyId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        setApiKeys(prev => prev.filter(key => key.id !== keyId));
        toast({
          title: "Success",
          description: "API key revoked successfully",
        });
      } else {
        throw new Error("Failed to revoke API key");
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to revoke API key",
        variant: "destructive",
      });
    }
  };

  const copyToClipboard = async (text: string, keyId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(keyId);
      setTimeout(() => setCopiedKey(null), 2000);
      toast({
        title: "Copied",
        description: "API key copied to clipboard",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to copy to clipboard",
        variant: "destructive",
      });
    }
  };

  const getCurlExamples = (apiKey: string) => {
    const baseUrl = window.location.origin;
    return {
      analyze: `curl -X POST "${baseUrl}/api/v1/analyze" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${apiKey}" \\
  -d '{
    "repo_path": "./my-project",
    "edge_types": ["imports", "calls", "extends"]
  }'`,

      graph: `curl "${baseUrl}/api/v1/graph/g_abc123def456" \\
  -H "Authorization: Bearer ${apiKey}"`,

      search: `curl "${baseUrl}/api/v1/search?repo_id=repo_abc123&query=function" \\
  -H "Authorization: Bearer ${apiKey}"`,

      context: `curl -X POST "${baseUrl}/api/v1/context" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${apiKey}" \\
  -d '{
    "repo_id": "repo_abc123",
    "task": "Fix the bug in authentication",
    "entry_points": ["src/auth.py"],
    "depth": 2
  }'`
    };
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Key className="w-8 h-8" />
          API Keys
        </h1>
        <p className="text-muted-foreground">
          Manage your API keys for accessing Codex Aura programmatically
        </p>
      </div>

      {/* Generate New Key */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Generate New API Key
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <Label htmlFor="key-name">Key Name</Label>
              <Input
                id="key-name"
                placeholder="e.g., Development Key, CI/CD Key"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && generateApiKey()}
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={generateApiKey}
                disabled={loading || !newKeyName.trim()}
              >
                {loading ? "Generating..." : "Generate Key"}
              </Button>
            </div>
          </div>

          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              <strong>Important:</strong> Copy your API key immediately after generation.
              It will not be shown again for security reasons.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* API Keys List */}
      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          {apiKeys.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Key className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No API keys yet. Generate your first key above.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {apiKeys.map((apiKey) => (
                <div key={apiKey.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold">{apiKey.name}</h3>
                        <Badge variant="secondary">
                          Created {new Date(apiKey.created_at).toLocaleDateString()}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span>Usage: {apiKey.usage_count} requests</span>
                        {apiKey.last_used && (
                          <span>Last used: {new Date(apiKey.last_used).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => revokeApiKey(apiKey.id)}
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      Revoke
                    </Button>
                  </div>

                  {/* API Key Display */}
                  <div className="bg-muted p-3 rounded font-mono text-sm mb-4">
                    <div className="flex items-center justify-between">
                      <span className="truncate">{apiKey.key}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(apiKey.key, apiKey.id)}
                      >
                        {copiedKey === apiKey.id ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* cURL Examples */}
                  <details className="mb-4">
                    <summary className="cursor-pointer flex items-center gap-2 text-sm font-medium">
                      <Code className="w-4 h-4" />
                      cURL Examples
                    </summary>
                    <div className="mt-4 space-y-4">
                      {Object.entries(getCurlExamples(apiKey.key)).map(([name, example]) => (
                        <div key={name}>
                          <h4 className="text-sm font-medium mb-2 capitalize">{name} API</h4>
                          <Textarea
                            value={example}
                            readOnly
                            className="font-mono text-xs h-24"
                          />
                          <Button
                            variant="outline"
                            size="sm"
                            className="mt-2"
                            onClick={() => copyToClipboard(example, `${apiKey.id}-${name}`)}
                          >
                            <Copy className="w-4 h-4 mr-2" />
                            Copy cURL
                          </Button>
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Usage Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>Usage Instructions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="font-semibold mb-2">Authentication</h3>
            <p className="text-sm text-muted-foreground mb-2">
              Include your API key in the Authorization header for all API requests:
            </p>
            <code className="block bg-muted p-2 rounded text-sm">
              Authorization: Bearer YOUR_API_KEY
            </code>
          </div>

          <div>
            <h3 className="font-semibold mb-2">Rate Limits</h3>
            <p className="text-sm text-muted-foreground">
              API keys are subject to rate limiting. Check the response headers for rate limit information.
            </p>
          </div>

          <div>
            <h3 className="font-semibold mb-2">Security</h3>
            <p className="text-sm text-muted-foreground">
              Keep your API keys secure and never share them publicly. Revoke keys immediately if they are compromised.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}