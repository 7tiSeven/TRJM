"use client";

import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  File,
  FileText,
  FileSpreadsheet,
  Mail,
  Download,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { filesAPI, glossaryAPI, FileTranslationResponse, Glossary } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { cn, formatFileSize, getConfidenceLevel } from "@/lib/utils";
import { useFeature, Features } from "@/lib/auth";

const stylePresets = [
  { value: "neutral", label: "Neutral" },
  { value: "formal", label: "Formal" },
  { value: "casual", label: "Casual" },
  { value: "technical", label: "Technical" },
  { value: "literary", label: "Literary" },
];

const targetLanguages = [
  { value: "ar", label: "Arabic (MSA)" },
  { value: "en", label: "English" },
];

interface UploadedFile {
  file: File;
  status: "pending" | "uploading" | "processing" | "completed" | "failed";
  progress: number;
  result?: FileTranslationResponse;
  error?: string;
}

const fileIcons: Record<string, React.ElementType> = {
  ".txt": FileText,
  ".docx": File,
  ".pdf": FileSpreadsheet,
  ".msg": Mail,
};

function getFileIcon(filename: string) {
  const ext = "." + filename.split(".").pop()?.toLowerCase();
  return fileIcons[ext] || File;
}

export default function FilesPage() {
  const { toast } = useToast();
  const canUseGlossary = useFeature(Features.USE_GLOSSARY);

  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [targetLanguage, setTargetLanguage] = useState("ar");
  const [stylePreset, setStylePreset] = useState("neutral");
  const [glossaryId, setGlossaryId] = useState<string | undefined>();
  const [glossaries, setGlossaries] = useState<Glossary[]>([]);
  const [supportedFormats, setSupportedFormats] = useState<string[]>([]);
  const [maxSizeMb, setMaxSizeMb] = useState(10);

  // Load glossaries and supported formats
  useEffect(() => {
    if (canUseGlossary) {
      glossaryAPI.list()
        .then((res) => setGlossaries(res?.glossaries || []))
        .catch(console.error);
    }
    filesAPI.getSupportedFormats()
      .then((res) => {
        setSupportedFormats(res?.formats?.map((f) => f.extension) || []);
        setMaxSizeMb(res?.max_size_mb || 10);
      })
      .catch(console.error);
  }, [canUseGlossary]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: UploadedFile[] = acceptedFiles.map((file) => ({
      file,
      status: "pending" as const,
      progress: 0,
    }));
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/plain": [".txt"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "application/pdf": [".pdf"],
      "application/vnd.ms-outlook": [".msg"],
    },
    maxSize: maxSizeMb * 1024 * 1024,
  });

  const uploadFile = async (index: number) => {
    const uploadedFile = files[index];
    if (!uploadedFile || uploadedFile.status !== "pending") return;

    // Update status to uploading
    setFiles((prev) =>
      prev.map((f, i) =>
        i === index ? { ...f, status: "uploading" as const, progress: 20 } : f
      )
    );

    try {
      // Upload and translate
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index ? { ...f, status: "processing" as const, progress: 50 } : f
        )
      );

      const result = await filesAPI.translate(
        uploadedFile.file,
        targetLanguage,
        stylePreset,
        glossaryId
      );

      // Poll for status if still processing
      let finalResult = result;
      if (result.status === "processing") {
        // Poll every 2 seconds
        for (let i = 0; i < 60; i++) {
          await new Promise((resolve) => setTimeout(resolve, 2000));
          finalResult = await filesAPI.getStatus(result.job_id);

          setFiles((prev) =>
            prev.map((f, idx) =>
              idx === index ? { ...f, progress: 50 + Math.min(i * 2, 40) } : f
            )
          );

          if (finalResult.status === "completed" || finalResult.status === "failed") {
            break;
          }
        }
      }

      setFiles((prev) =>
        prev.map((f, i) =>
          i === index
            ? {
                ...f,
                status: finalResult.status === "completed" ? "completed" : "failed",
                progress: 100,
                result: finalResult,
                error: finalResult.error_message,
              }
            : f
        )
      );
    } catch (error) {
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index
            ? {
                ...f,
                status: "failed" as const,
                progress: 100,
                error: error instanceof Error ? error.message : "Upload failed",
              }
            : f
        )
      );
    }
  };

  const uploadAllPending = () => {
    files.forEach((_, index) => {
      if (files[index].status === "pending") {
        uploadFile(index);
      }
    });
  };

  const downloadFile = async (jobId: string, filename: string) => {
    try {
      const blob = await filesAPI.download(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: "Download Failed",
        description: error instanceof Error ? error.message : "Could not download file",
        variant: "destructive",
      });
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const pendingCount = files.filter((f) => f.status === "pending").length;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">File Translation</h1>
          <p className="text-muted-foreground">
            Upload documents for translation. Supported formats: {supportedFormats.join(", ")}
          </p>
        </div>

        {/* Options */}
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
                    {lang.label}
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
                    {preset.label}
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
                      {glossary.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {pendingCount > 0 && (
            <Button onClick={uploadAllPending} className="gap-2">
              <Upload className="h-4 w-4" />
              Translate {pendingCount} File{pendingCount > 1 ? "s" : ""}
            </Button>
          )}
        </div>

        {/* Upload Zone */}
        <Card>
          <CardContent className="pt-6">
            <div
              {...getRootProps()}
              className={cn(
                "upload-zone cursor-pointer",
                isDragActive && "upload-zone-active"
              )}
            >
              <input {...getInputProps()} />
              <div className="flex flex-col items-center gap-3">
                <Upload className="h-10 w-10 text-muted-foreground" />
                {isDragActive ? (
                  <p className="text-lg">Drop files here...</p>
                ) : (
                  <>
                    <p className="text-lg">Drag and drop files here, or click to select</p>
                    <p className="text-sm text-muted-foreground">
                      Max file size: {maxSizeMb}MB | Supported: {supportedFormats.join(", ")}
                    </p>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* File List */}
        {files.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Uploaded Files</CardTitle>
              <CardDescription>
                {files.filter((f) => f.status === "completed").length} of {files.length} completed
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {files.map((uploadedFile, index) => {
                  const Icon = getFileIcon(uploadedFile.file.name);
                  const confidenceInfo = uploadedFile.result?.confidence
                    ? getConfidenceLevel(uploadedFile.result.confidence)
                    : null;

                  return (
                    <div
                      key={index}
                      className="flex items-center gap-4 p-4 rounded-lg border bg-card"
                    >
                      <Icon className="h-8 w-8 text-muted-foreground shrink-0" />

                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{uploadedFile.file.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {formatFileSize(uploadedFile.file.size)}
                        </p>

                        {(uploadedFile.status === "uploading" || uploadedFile.status === "processing") && (
                          <Progress value={uploadedFile.progress} className="mt-2 h-1" />
                        )}

                        {uploadedFile.error && (
                          <p className="text-sm text-destructive mt-1">{uploadedFile.error}</p>
                        )}
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {/* Status Icon */}
                        {uploadedFile.status === "pending" && (
                          <Clock className="h-5 w-5 text-muted-foreground" />
                        )}
                        {(uploadedFile.status === "uploading" || uploadedFile.status === "processing") && (
                          <Loader2 className="h-5 w-5 text-primary animate-spin" />
                        )}
                        {uploadedFile.status === "completed" && (
                          <CheckCircle2 className="h-5 w-5 text-green-500" />
                        )}
                        {uploadedFile.status === "failed" && (
                          <XCircle className="h-5 w-5 text-destructive" />
                        )}

                        {/* Confidence Badge */}
                        {confidenceInfo && (
                          <span className={cn("confidence-indicator text-xs", confidenceInfo.className)}>
                            {Math.round((uploadedFile.result?.confidence || 0) * 100)}%
                          </span>
                        )}

                        {/* Actions */}
                        {uploadedFile.status === "pending" && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => uploadFile(index)}
                            >
                              Translate
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeFile(index)}
                            >
                              Remove
                            </Button>
                          </>
                        )}

                        {uploadedFile.status === "completed" && uploadedFile.result?.download_ready && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              downloadFile(
                                uploadedFile.result!.job_id,
                                uploadedFile.result!.translated_file_name || "translated"
                              )
                            }
                            className="gap-1"
                          >
                            <Download className="h-4 w-4" />
                            Download
                          </Button>
                        )}

                        {uploadedFile.status === "failed" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setFiles((prev) =>
                                prev.map((f, i) =>
                                  i === index
                                    ? { ...f, status: "pending" as const, progress: 0, error: undefined }
                                    : f
                                )
                              );
                            }}
                          >
                            Retry
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
