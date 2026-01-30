"use client";

import { useState, useEffect } from "react";
import {
  Plus,
  Trash2,
  Edit2,
  Upload,
  Download,
  Book,
  Search,
  Loader2,
} from "lucide-react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { glossaryAPI, Glossary, GlossaryEntry } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { useFeature, Features } from "@/lib/auth";
import { formatDate } from "@/lib/utils";

export default function GlossaryPage() {
  const { toast } = useToast();
  const canManage = useFeature(Features.MANAGE_GLOSSARY);

  const [glossaries, setGlossaries] = useState<Glossary[]>([]);
  const [selectedGlossary, setSelectedGlossary] = useState<Glossary | null>(null);
  const [entries, setEntries] = useState<GlossaryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEntriesLoading, setIsEntriesLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  // Dialog states
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEntryDialog, setShowEntryDialog] = useState(false);
  const [editingEntry, setEditingEntry] = useState<GlossaryEntry | null>(null);

  // Form states
  const [glossaryName, setGlossaryName] = useState("");
  const [glossaryDescription, setGlossaryDescription] = useState("");
  const [entrySource, setEntrySource] = useState("");
  const [entryTarget, setEntryTarget] = useState("");
  const [entryContext, setEntryContext] = useState("");

  const loadGlossaries = async () => {
    setIsLoading(true);
    try {
      const response = await glossaryAPI.list();
      const loadedGlossaries = response?.glossaries || [];
      setGlossaries(loadedGlossaries);
      if (loadedGlossaries.length > 0 && !selectedGlossary) {
        setSelectedGlossary(loadedGlossaries[0]);
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load glossaries",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const loadEntries = async (glossaryId: string) => {
    setIsEntriesLoading(true);
    try {
      const response = await glossaryAPI.getEntries(glossaryId);
      setEntries(response?.entries || []);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load entries",
        variant: "destructive",
      });
    } finally {
      setIsEntriesLoading(false);
    }
  };

  useEffect(() => {
    loadGlossaries();
  }, []);

  useEffect(() => {
    if (selectedGlossary) {
      loadEntries(selectedGlossary.id);
    }
  }, [selectedGlossary]);

  const handleCreateGlossary = async () => {
    try {
      const newGlossary = await glossaryAPI.create({
        name: glossaryName,
        description: glossaryDescription,
      });
      setGlossaries((prev) => [...prev, newGlossary]);
      setSelectedGlossary(newGlossary);
      setShowCreateDialog(false);
      setGlossaryName("");
      setGlossaryDescription("");
      toast({ title: "Success", description: "Glossary created" });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create glossary",
        variant: "destructive",
      });
    }
  };

  const handleDeleteGlossary = async (glossaryId: string) => {
    if (!confirm("Are you sure you want to delete this glossary?")) return;

    try {
      await glossaryAPI.delete(glossaryId);
      setGlossaries((prev) => prev.filter((g) => g.id !== glossaryId));
      if (selectedGlossary?.id === glossaryId) {
        setSelectedGlossary(glossaries[0] || null);
      }
      toast({ title: "Success", description: "Glossary deleted" });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete glossary",
        variant: "destructive",
      });
    }
  };

  const handleSaveEntry = async () => {
    if (!selectedGlossary) return;

    try {
      if (editingEntry) {
        const updated = await glossaryAPI.updateEntry(
          selectedGlossary.id,
          editingEntry.id,
          { source_term: entrySource, target_term: entryTarget, context: entryContext }
        );
        setEntries((prev) =>
          prev.map((e) => (e.id === editingEntry.id ? updated : e))
        );
      } else {
        const newEntry = await glossaryAPI.addEntry(selectedGlossary.id, {
          source_term: entrySource,
          target_term: entryTarget,
          context: entryContext,
        });
        setEntries((prev) => [...prev, newEntry]);
      }

      setShowEntryDialog(false);
      setEditingEntry(null);
      setEntrySource("");
      setEntryTarget("");
      setEntryContext("");
      toast({ title: "Success", description: "Entry saved" });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save entry",
        variant: "destructive",
      });
    }
  };

  const handleDeleteEntry = async (entryId: string) => {
    if (!selectedGlossary) return;
    if (!confirm("Delete this entry?")) return;

    try {
      await glossaryAPI.deleteEntry(selectedGlossary.id, entryId);
      setEntries((prev) => prev.filter((e) => e.id !== entryId));
      toast({ title: "Success", description: "Entry deleted" });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete entry",
        variant: "destructive",
      });
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedGlossary || !e.target.files?.[0]) return;

    try {
      const result = await glossaryAPI.importCSV(selectedGlossary.id, e.target.files[0]);
      toast({
        title: "Import Complete",
        description: `Imported ${result.imported} entries, skipped ${result.skipped}`,
      });
      loadEntries(selectedGlossary.id);
    } catch (error) {
      toast({
        title: "Import Failed",
        description: error instanceof Error ? error.message : "Failed to import CSV",
        variant: "destructive",
      });
    }
  };

  const handleExport = async () => {
    if (!selectedGlossary) return;

    try {
      const blob = await glossaryAPI.exportCSV(selectedGlossary.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${selectedGlossary.name}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: "Export Failed",
        description: "Failed to export glossary",
        variant: "destructive",
      });
    }
  };

  const openEntryDialog = (entry?: GlossaryEntry) => {
    if (entry) {
      setEditingEntry(entry);
      setEntrySource(entry.source_term);
      setEntryTarget(entry.target_term);
      setEntryContext(entry.context || "");
    } else {
      setEditingEntry(null);
      setEntrySource("");
      setEntryTarget("");
      setEntryContext("");
    }
    setShowEntryDialog(true);
  };

  const filteredEntries = entries.filter(
    (e) =>
      e.source_term.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.target_term.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Glossary Management</h1>
            <p className="text-muted-foreground">
              Manage terminology for consistent translations
            </p>
          </div>
          {canManage && (
            <Button onClick={() => setShowCreateDialog(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              New Glossary
            </Button>
          )}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : glossaries.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Book className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Glossaries</h3>
              <p className="text-muted-foreground mb-4">
                Create your first glossary to ensure consistent terminology
              </p>
              {canManage && (
                <Button onClick={() => setShowCreateDialog(true)}>
                  Create Glossary
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Glossary List */}
            <div className="lg:col-span-1">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Glossaries</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y">
                    {glossaries.map((glossary) => (
                      <div
                        key={glossary.id}
                        className={`p-4 cursor-pointer hover:bg-muted/50 transition-colors ${
                          selectedGlossary?.id === glossary.id ? "bg-muted" : ""
                        }`}
                        onClick={() => setSelectedGlossary(glossary)}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{glossary.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {glossary.entry_count} terms
                            </p>
                          </div>
                          {canManage && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteGlossary(glossary.id);
                              }}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Entries */}
            <div className="lg:col-span-3">
              {selectedGlossary && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>{selectedGlossary.name}</CardTitle>
                        <CardDescription>
                          {selectedGlossary.description || "No description"} |{" "}
                          Created {formatDate(selectedGlossary.created_at)}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        {canManage && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openEntryDialog()}
                              className="gap-1"
                            >
                              <Plus className="h-4 w-4" />
                              Add Term
                            </Button>
                            <label>
                              <Button
                                variant="outline"
                                size="sm"
                                className="gap-1"
                                asChild
                              >
                                <span>
                                  <Upload className="h-4 w-4" />
                                  Import
                                </span>
                              </Button>
                              <input
                                type="file"
                                accept=".csv"
                                className="hidden"
                                onChange={handleImport}
                              />
                            </label>
                          </>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleExport}
                          className="gap-1"
                        >
                          <Download className="h-4 w-4" />
                          Export
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {/* Search */}
                    <div className="mb-4">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="Search terms..."
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                          className="pl-9"
                        />
                      </div>
                    </div>

                    {/* Entries Table */}
                    {isEntriesLoading ? (
                      <div className="flex justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                      </div>
                    ) : filteredEntries.length === 0 ? (
                      <div className="text-center py-8 text-muted-foreground">
                        {entries.length === 0 ? "No entries yet" : "No matching entries"}
                      </div>
                    ) : (
                      <div className="border rounded-lg overflow-hidden">
                        <table className="w-full">
                          <thead className="bg-muted/50">
                            <tr>
                              <th className="px-4 py-3 text-left text-sm font-medium">
                                Source Term
                              </th>
                              <th className="px-4 py-3 text-left text-sm font-medium">
                                Target Term
                              </th>
                              <th className="px-4 py-3 text-left text-sm font-medium">
                                Context
                              </th>
                              {canManage && (
                                <th className="px-4 py-3 text-right text-sm font-medium">
                                  Actions
                                </th>
                              )}
                            </tr>
                          </thead>
                          <tbody className="divide-y">
                            {filteredEntries.map((entry) => (
                              <tr key={entry.id} className="hover:bg-muted/30">
                                <td className="px-4 py-3 text-sm font-medium">
                                  {entry.source_term}
                                </td>
                                <td className="px-4 py-3 text-sm font-arabic" dir="rtl">
                                  {entry.target_term}
                                </td>
                                <td className="px-4 py-3 text-sm text-muted-foreground">
                                  {entry.context || "-"}
                                </td>
                                {canManage && (
                                  <td className="px-4 py-3 text-right">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => openEntryDialog(entry)}
                                    >
                                      <Edit2 className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => handleDeleteEntry(entry.id)}
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </td>
                                )}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        )}

        {/* Create Glossary Dialog */}
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Glossary</DialogTitle>
              <DialogDescription>
                Create a new glossary to manage terminology
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={glossaryName}
                  onChange={(e) => setGlossaryName(e.target.value)}
                  placeholder="e.g., Technical Terms"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Textarea
                  id="description"
                  value={glossaryDescription}
                  onChange={(e) => setGlossaryDescription(e.target.value)}
                  placeholder="Describe the purpose of this glossary"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateGlossary} disabled={!glossaryName}>
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Entry Dialog */}
        <Dialog open={showEntryDialog} onOpenChange={setShowEntryDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingEntry ? "Edit Entry" : "Add Entry"}</DialogTitle>
              <DialogDescription>
                {editingEntry ? "Update the terminology entry" : "Add a new term to the glossary"}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="source">Source Term (English)</Label>
                <Input
                  id="source"
                  value={entrySource}
                  onChange={(e) => setEntrySource(e.target.value)}
                  placeholder="e.g., Machine Learning"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="target">Target Term (Arabic)</Label>
                <Input
                  id="target"
                  value={entryTarget}
                  onChange={(e) => setEntryTarget(e.target.value)}
                  placeholder="e.g., التعلم الآلي"
                  dir="rtl"
                  className="font-arabic"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="context">Context (optional)</Label>
                <Textarea
                  id="context"
                  value={entryContext}
                  onChange={(e) => setEntryContext(e.target.value)}
                  placeholder="When should this translation be used?"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowEntryDialog(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSaveEntry}
                disabled={!entrySource || !entryTarget}
              >
                {editingEntry ? "Update" : "Add"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
}
