"use client";

import { useState, useEffect } from "react";
import {
  Search,
  Filter,
  Eye,
  Trash2,
  Download,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  FileText,
  Languages,
} from "lucide-react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { historyAPI, Job } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { cn, formatRelativeTime, getConfidenceLevel, truncateText } from "@/lib/utils";

const statusIcons: Record<string, React.ElementType> = {
  pending: Clock,
  processing: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
};

const statusColors: Record<string, string> = {
  pending: "text-yellow-500",
  processing: "text-blue-500",
  completed: "text-green-500",
  failed: "text-red-500",
};

export default function HistoryPage() {
  const { toast } = useToast();

  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [stats, setStats] = useState<{
    total_jobs: number;
    completed_jobs: number;
    failed_jobs: number;
    avg_confidence: number;
  } | null>(null);

  const loadJobs = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, unknown> = { page, limit };
      if (search) params.search = search;
      if (statusFilter !== "all") params.status = statusFilter;
      if (typeFilter !== "all") params.job_type = typeFilter;

      const response = await historyAPI.getJobs(params as Parameters<typeof historyAPI.getJobs>[0]);
      setJobs(response?.jobs || []);
      setTotal(response?.total || 0);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load history",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await historyAPI.getStats();
      setStats(response);
    } catch (error) {
      console.error("Failed to load stats", error);
    }
  };

  useEffect(() => {
    loadJobs();
    loadStats();
  }, [page, statusFilter, typeFilter]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      if (page === 1) {
        loadJobs();
      } else {
        setPage(1);
      }
    }, 300);
    return () => clearTimeout(debounce);
  }, [search]);

  const handleDelete = async (jobId: string) => {
    if (!confirm("Are you sure you want to delete this job?")) return;

    try {
      await historyAPI.deleteJob(jobId);
      toast({ title: "Success", description: "Job deleted" });
      loadJobs();
      loadStats();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete job",
        variant: "destructive",
      });
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">Translation History</h1>
          <p className="text-muted-foreground">
            View and manage your past translations
          </p>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-3xl font-bold">{stats.total_jobs}</p>
                  <p className="text-sm text-muted-foreground">Total Jobs</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-500">{stats.completed_jobs}</p>
                  <p className="text-sm text-muted-foreground">Completed</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-3xl font-bold text-red-500">{stats.failed_jobs}</p>
                  <p className="text-sm text-muted-foreground">Failed</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <p className="text-3xl font-bold">
                    {Math.round(stats.avg_confidence * 100)}%
                  </p>
                  <p className="text-sm text-muted-foreground">Avg Confidence</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search translations..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>

          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="text">Text</SelectItem>
              <SelectItem value="file">File</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Jobs List */}
        <Card>
          <CardHeader>
            <CardTitle>Jobs</CardTitle>
            <CardDescription>
              Showing {jobs.length} of {total} results
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground">No translation history found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => {
                  const StatusIcon = statusIcons[job.status] || Clock;
                  const confidenceInfo = job.confidence ? getConfidenceLevel(job.confidence) : null;

                  return (
                    <div
                      key={job.id}
                      className="flex items-center gap-4 p-4 rounded-lg border hover:bg-muted/50 transition-colors"
                    >
                      {/* Type Icon */}
                      {job.job_type === "file" ? (
                        <FileText className="h-6 w-6 text-muted-foreground" />
                      ) : (
                        <Languages className="h-6 w-6 text-muted-foreground" />
                      )}

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">
                          {job.file_name || truncateText(job.input_text || "No content", 50)}
                        </p>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span>{job.source_language} → {job.target_language}</span>
                          <span>|</span>
                          <span>{formatRelativeTime(job.created_at)}</span>
                        </div>
                      </div>

                      {/* Status */}
                      <div className="flex items-center gap-2">
                        <StatusIcon
                          className={cn(
                            "h-5 w-5",
                            statusColors[job.status],
                            job.status === "processing" && "animate-spin"
                          )}
                        />
                        {confidenceInfo && (
                          <span className={cn("confidence-indicator text-xs", confidenceInfo.className)}>
                            {Math.round(job.confidence! * 100)}%
                          </span>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setSelectedJob(job)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(job.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={page === totalPages}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Job Detail Dialog */}
        <Dialog open={!!selectedJob} onOpenChange={() => setSelectedJob(null)}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Translation Details</DialogTitle>
              <DialogDescription>
                Job ID: {selectedJob?.id}
              </DialogDescription>
            </DialogHeader>

            {selectedJob && (
              <div className="space-y-4">
                {/* Metadata */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Status</p>
                    <p className="font-medium capitalize">{selectedJob.status}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Type</p>
                    <p className="font-medium capitalize">{selectedJob.job_type}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Languages</p>
                    <p className="font-medium">
                      {selectedJob.source_language} → {selectedJob.target_language}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Confidence</p>
                    <p className="font-medium">
                      {selectedJob.confidence
                        ? `${Math.round(selectedJob.confidence * 100)}%`
                        : "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Created</p>
                    <p className="font-medium">{new Date(selectedJob.created_at).toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Completed</p>
                    <p className="font-medium">
                      {selectedJob.completed_at
                        ? new Date(selectedJob.completed_at).toLocaleString()
                        : "N/A"}
                    </p>
                  </div>
                </div>

                <Separator />

                {/* Input */}
                {selectedJob.input_text && (
                  <div>
                    <p className="text-sm font-medium mb-2">Source Text</p>
                    <div className="p-3 rounded-md bg-muted/50 text-sm whitespace-pre-wrap">
                      {selectedJob.input_text}
                    </div>
                  </div>
                )}

                {/* Output */}
                {selectedJob.output_text && (
                  <div>
                    <p className="text-sm font-medium mb-2">Translation</p>
                    <div
                      className="p-3 rounded-md bg-muted/50 text-sm whitespace-pre-wrap"
                      dir={selectedJob.target_language === "ar" ? "rtl" : "ltr"}
                    >
                      {selectedJob.output_text}
                    </div>
                  </div>
                )}

                {/* Error */}
                {selectedJob.error_message && (
                  <div>
                    <p className="text-sm font-medium mb-2 text-destructive">Error</p>
                    <div className="p-3 rounded-md bg-destructive/10 text-sm text-destructive">
                      {selectedJob.error_message}
                    </div>
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
}
