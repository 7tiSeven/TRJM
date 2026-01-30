"use client";

import { useState, useEffect } from "react";
import { Languages, Copy, Check, RefreshCw, Wand2 } from "lucide-react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { translationAPI, glossaryAPI, TranslationResponse, Glossary, QAIssue } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { cn, getConfidenceLevel, getTextDirection } from "@/lib/utils";
import { useFeature, Features } from "@/lib/auth";

const stylePresets = [
  { value: "neutral", label: "Neutral", description: "Balanced, standard translation" },
  { value: "formal", label: "Formal", description: "Professional, business-appropriate" },
  { value: "casual", label: "Casual", description: "Conversational, friendly tone" },
  { value: "technical", label: "Technical", description: "Precise, domain-specific terminology" },
  { value: "literary", label: "Literary", description: "Eloquent, preserving artistic style" },
];

const targetLanguages = [
  { value: "ar", label: "Arabic (MSA)", native: "العربية" },
  { value: "en", label: "English", native: "English" },
];

export default function TranslatePage() {
  const { toast } = useToast();
  const canUseGlossary = useFeature(Features.USE_GLOSSARY);

  const [sourceText, setSourceText] = useState("");
  const [targetLanguage, setTargetLanguage] = useState("ar");
  const [stylePreset, setStylePreset] = useState("neutral");
  const [glossaryId, setGlossaryId] = useState<string | undefined>();
  const [glossaries, setGlossaries] = useState<Glossary[]>([]);
  const [result, setResult] = useState<TranslationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  // Load glossaries
  useEffect(() => {
    if (canUseGlossary) {
      glossaryAPI.list()
        .then((res) => setGlossaries(res?.glossaries || []))
        .catch(console.error);
    }
  }, [canUseGlossary]);

  const handleTranslate = async () => {
    if (!sourceText.trim()) {
      toast({
        title: "Error",
        description: "Please enter text to translate",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    setResult(null);

    try {
      const response = await translationAPI.translate({
        text: sourceText,
        target_language: targetLanguage,
        style_preset: stylePreset,
        glossary_id: glossaryId,
      });
      setResult(response);
    } catch (error) {
      toast({
        title: "Translation Failed",
        description: error instanceof Error ? error.message : "An error occurred",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = async () => {
    if (result?.translation) {
      await navigator.clipboard.writeText(result.translation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSwapLanguages = () => {
    if (result?.translation) {
      setSourceText(result.translation);
      setTargetLanguage(targetLanguage === "ar" ? "en" : "ar");
      setResult(null);
    }
  };

  const confidenceInfo = result?.confidence ? getConfidenceLevel(result.confidence) : null;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">Text Translation</h1>
          <p className="text-muted-foreground">
            Translate text between English and Arabic with AI-powered quality assurance
          </p>
        </div>

        {/* Options Bar */}
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-2">
            <Label>Target Language</Label>
            <Select value={targetLanguage} onValueChange={setTargetLanguage}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {targetLanguages.map((lang) => (
                  <SelectItem key={lang.value} value={lang.value}>
                    <span className="flex items-center gap-2">
                      {lang.label}
                      <span className="text-muted-foreground text-xs">
                        ({lang.native})
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Style Preset</Label>
            <Select value={stylePreset} onValueChange={setStylePreset}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {stylePresets.map((preset) => (
                  <SelectItem key={preset.value} value={preset.value}>
                    <div className="flex flex-col">
                      <span>{preset.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {preset.description}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {canUseGlossary && glossaries && glossaries.length > 0 && (
            <div className="space-y-2">
              <Label>Glossary</Label>
              <Select value={glossaryId || "none"} onValueChange={(v) => setGlossaryId(v === "none" ? undefined : v)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select glossary" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No glossary</SelectItem>
                  {glossaries.map((glossary) => (
                    <SelectItem key={glossary.id} value={glossary.id}>
                      {glossary.name} ({glossary.entry_count} terms)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <Button onClick={handleTranslate} disabled={isLoading} className="gap-2">
            {isLoading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Translating...
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4" />
                Translate
              </>
            )}
          </Button>
        </div>

        {/* Split Pane Editor */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Source Panel */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Source Text</CardTitle>
                <span className="text-sm text-muted-foreground">
                  {sourceText.length} characters
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <Textarea
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value)}
                placeholder="Enter text to translate..."
                className="min-h-[300px] resize-none"
                dir={getTextDirection(sourceText)}
              />
            </CardContent>
          </Card>

          {/* Target Panel */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Translation</CardTitle>
                <div className="flex items-center gap-2">
                  {result && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleSwapLanguages}
                        title="Use translation as source"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleCopy}
                      >
                        {copied ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div
                className={cn(
                  "min-h-[300px] rounded-md border bg-muted/30 p-4",
                  targetLanguage === "ar" && "font-arabic"
                )}
                dir={targetLanguage === "ar" ? "rtl" : "ltr"}
              >
                {isLoading ? (
                  <div className="flex h-full items-center justify-center">
                    <div className="flex flex-col items-center gap-3">
                      <div className="spinner h-8 w-8" />
                      <p className="text-sm text-muted-foreground">Processing translation...</p>
                    </div>
                  </div>
                ) : result ? (
                  <p className="whitespace-pre-wrap leading-relaxed">
                    {result.translation}
                  </p>
                ) : (
                  <p className="text-muted-foreground">
                    Translation will appear here...
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* QA Report */}
        {result && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Quality Report</CardTitle>
                {confidenceInfo && (
                  <div className={cn("confidence-indicator", confidenceInfo.className)}>
                    <span>{Math.round(result.confidence * 100)}%</span>
                    <span>{confidenceInfo.label}</span>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 rounded-lg bg-muted/50">
                    <p className="text-2xl font-bold">{Math.round(result.confidence * 100)}%</p>
                    <p className="text-xs text-muted-foreground">Confidence</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted/50">
                    <p className="text-2xl font-bold">
                      {Math.round((result.qa_report?.glossary_compliance || 0) * 100)}%
                    </p>
                    <p className="text-xs text-muted-foreground">Glossary Compliance</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted/50">
                    <p className="text-2xl font-bold">{result.qa_report?.issues?.length || 0}</p>
                    <p className="text-xs text-muted-foreground">Issues Found</p>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-muted/50">
                    <p className="text-2xl font-bold">{result.processing_time_ms}ms</p>
                    <p className="text-xs text-muted-foreground">Processing Time</p>
                  </div>
                </div>

                {/* Issues List */}
                {result.qa_report?.issues && result.qa_report.issues.length > 0 && (
                  <>
                    <Separator />
                    <div>
                      <h4 className="font-medium mb-3">Issues</h4>
                      <div className="space-y-2">
                        {result.qa_report.issues.map((issue: QAIssue, index: number) => (
                          <div
                            key={index}
                            className={cn(
                              "qa-issue",
                              issue.severity === "critical" && "qa-issue-critical",
                              issue.severity === "major" && "qa-issue-major",
                              issue.severity === "minor" && "qa-issue-minor",
                              issue.severity === "suggestion" && "qa-issue-suggestion"
                            )}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <span className="font-medium capitalize">{issue.type}</span>
                                <span className="mx-2 text-muted-foreground">|</span>
                                <span className="text-sm capitalize text-muted-foreground">
                                  {issue.severity}
                                </span>
                              </div>
                            </div>
                            <p className="text-sm mt-1">{issue.message}</p>
                            {issue.suggestion && (
                              <p className="text-sm text-muted-foreground mt-1">
                                Suggestion: {issue.suggestion}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
