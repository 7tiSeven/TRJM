"use client";

import { useState, useEffect } from "react";
import {
  Users,
  Shield,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  Loader2,
  Search,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { adminAPI, Role, User } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/utils";

const allFeatures = [
  { name: "translate_text", description: "Translate text content" },
  { name: "upload_files", description: "Upload files for translation" },
  { name: "translate_docx", description: "Translate Word documents" },
  { name: "translate_pdf", description: "Translate PDF files" },
  { name: "translate_msg", description: "Translate Outlook emails" },
  { name: "use_glossary", description: "Use glossaries in translations" },
  { name: "manage_glossary", description: "Create and manage glossaries" },
  { name: "view_history", description: "View translation history" },
  { name: "export_results", description: "Export translation results" },
  { name: "admin_panel", description: "Access admin panel" },
];

export default function AdminPage() {
  const { toast } = useToast();

  const [roles, setRoles] = useState<Role[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoadingRoles, setIsLoadingRoles] = useState(true);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
  const [userSearch, setUserSearch] = useState("");
  const [userPage, setUserPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);

  // Dialog states
  const [showRoleDialog, setShowRoleDialog] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [roleName, setRoleName] = useState("");
  const [roleDescription, setRoleDescription] = useState("");
  const [roleFeatures, setRoleFeatures] = useState<string[]>([]);

  const loadRoles = async () => {
    setIsLoadingRoles(true);
    try {
      const response = await adminAPI.getRoles();
      setRoles(response.roles);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load roles",
        variant: "destructive",
      });
    } finally {
      setIsLoadingRoles(false);
    }
  };

  const loadUsers = async () => {
    setIsLoadingUsers(true);
    try {
      const response = await adminAPI.getUsers({
        page: userPage,
        limit: 10,
        search: userSearch || undefined,
      });
      setUsers(response.users);
      setTotalUsers(response.total);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load users",
        variant: "destructive",
      });
    } finally {
      setIsLoadingUsers(false);
    }
  };

  useEffect(() => {
    loadRoles();
  }, []);

  useEffect(() => {
    loadUsers();
  }, [userPage]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      if (userPage === 1) {
        loadUsers();
      } else {
        setUserPage(1);
      }
    }, 300);
    return () => clearTimeout(debounce);
  }, [userSearch]);

  const openRoleDialog = (role?: Role) => {
    if (role) {
      setEditingRole(role);
      setRoleName(role.name);
      setRoleDescription(role.description || "");
      setRoleFeatures(role.features);
    } else {
      setEditingRole(null);
      setRoleName("");
      setRoleDescription("");
      setRoleFeatures([]);
    }
    setShowRoleDialog(true);
  };

  const handleSaveRole = async () => {
    try {
      if (editingRole) {
        const updated = await adminAPI.updateRole(editingRole.id, {
          name: roleName,
          description: roleDescription,
          features: roleFeatures,
        });
        setRoles((prev) =>
          prev.map((r) => (r.id === editingRole.id ? updated : r))
        );
      } else {
        const newRole = await adminAPI.createRole({
          name: roleName,
          description: roleDescription,
          features: roleFeatures,
        });
        setRoles((prev) => [...prev, newRole]);
      }
      setShowRoleDialog(false);
      toast({ title: "Success", description: "Role saved" });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save role",
        variant: "destructive",
      });
    }
  };

  const handleDeleteRole = async (roleId: string) => {
    if (!confirm("Are you sure you want to delete this role?")) return;

    try {
      await adminAPI.deleteRole(roleId);
      setRoles((prev) => prev.filter((r) => r.id !== roleId));
      toast({ title: "Success", description: "Role deleted" });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete role",
        variant: "destructive",
      });
    }
  };

  const handleUpdateUserRole = async (userId: string, roleId: string) => {
    try {
      await adminAPI.updateUserRole(userId, roleId);
      loadUsers();
      toast({ title: "Success", description: "User role updated" });
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update user role",
        variant: "destructive",
      });
    }
  };

  const toggleFeature = (feature: string) => {
    setRoleFeatures((prev) =>
      prev.includes(feature)
        ? prev.filter((f) => f !== feature)
        : [...prev, feature]
    );
  };

  const totalUserPages = Math.ceil(totalUsers / 10);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold">Administration</h1>
          <p className="text-muted-foreground">
            Manage users, roles, and system settings
          </p>
        </div>

        <Tabs defaultValue="roles">
          <TabsList>
            <TabsTrigger value="roles" className="gap-2">
              <Shield className="h-4 w-4" />
              Roles
            </TabsTrigger>
            <TabsTrigger value="users" className="gap-2">
              <Users className="h-4 w-4" />
              Users
            </TabsTrigger>
          </TabsList>

          {/* Roles Tab */}
          <TabsContent value="roles" className="space-y-4">
            <div className="flex justify-end">
              <Button onClick={() => openRoleDialog()} className="gap-2">
                <Plus className="h-4 w-4" />
                New Role
              </Button>
            </div>

            {isLoadingRoles ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {roles.map((role) => (
                  <Card key={role.id}>
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div>
                          <CardTitle className="text-lg flex items-center gap-2">
                            {role.name}
                            {role.is_default && (
                              <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                                Default
                              </span>
                            )}
                          </CardTitle>
                          <CardDescription>{role.description}</CardDescription>
                        </div>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openRoleDialog(role)}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          {!role.is_default && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteRole(role.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-2">
                        Features ({role.features?.length || 0})
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {(role.features || []).slice(0, 5).map((feature) => (
                          <span
                            key={feature}
                            className="text-xs bg-muted px-2 py-1 rounded"
                          >
                            {feature.replace(/_/g, " ")}
                          </span>
                        ))}
                        {(role.features?.length || 0) > 5 && (
                          <span className="text-xs text-muted-foreground px-2 py-1">
                            +{(role.features?.length || 0) - 5} more
                          </span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Users Tab */}
          <TabsContent value="users" className="space-y-4">
            <div className="flex gap-4">
              <div className="flex-1 max-w-sm">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search users..."
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>
            </div>

            <Card>
              <CardContent className="pt-6">
                {isLoadingUsers ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : users.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    No users found
                  </div>
                ) : (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="px-4 py-3 text-left text-sm font-medium">
                            User
                          </th>
                          <th className="px-4 py-3 text-left text-sm font-medium">
                            Email
                          </th>
                          <th className="px-4 py-3 text-left text-sm font-medium">
                            Role
                          </th>
                          <th className="px-4 py-3 text-left text-sm font-medium">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {users.map((user) => (
                          <tr key={user.id} className="hover:bg-muted/30">
                            <td className="px-4 py-3">
                              <div>
                                <p className="font-medium">{user.display_name}</p>
                                <p className="text-sm text-muted-foreground">
                                  @{user.username}
                                </p>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-sm">{user.email}</td>
                            <td className="px-4 py-3">
                              <Select
                                value={user.role.id}
                                onValueChange={(roleId) =>
                                  handleUpdateUserRole(user.id, roleId)
                                }
                              >
                                <SelectTrigger className="w-[150px]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {roles.map((role) => (
                                    <SelectItem key={role.id} value={role.id}>
                                      {role.name}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </td>
                            <td className="px-4 py-3">
                              <span className="text-sm text-muted-foreground">
                                {user.features?.length || 0} features
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Pagination */}
                {totalUserPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-6">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setUserPage(userPage - 1)}
                      disabled={userPage === 1}
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {userPage} of {totalUserPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setUserPage(userPage + 1)}
                      disabled={userPage === totalUserPages}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Role Dialog */}
        <Dialog open={showRoleDialog} onOpenChange={setShowRoleDialog}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{editingRole ? "Edit Role" : "Create Role"}</DialogTitle>
              <DialogDescription>
                {editingRole
                  ? "Update the role configuration"
                  : "Create a new role with specific permissions"}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="roleName">Role Name</Label>
                  <Input
                    id="roleName"
                    value={roleName}
                    onChange={(e) => setRoleName(e.target.value)}
                    placeholder="e.g., Editor"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="roleDesc">Description</Label>
                  <Input
                    id="roleDesc"
                    value={roleDescription}
                    onChange={(e) => setRoleDescription(e.target.value)}
                    placeholder="Brief description"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Features</Label>
                <div className="border rounded-lg p-4 max-h-[300px] overflow-y-auto">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {allFeatures.map((feature) => (
                      <div
                        key={feature.name}
                        className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                          roleFeatures.includes(feature.name)
                            ? "bg-primary/10 border border-primary/20"
                            : "bg-muted/50 hover:bg-muted"
                        }`}
                        onClick={() => toggleFeature(feature.name)}
                      >
                        <div
                          className={`w-5 h-5 rounded flex items-center justify-center ${
                            roleFeatures.includes(feature.name)
                              ? "bg-primary text-primary-foreground"
                              : "border"
                          }`}
                        >
                          {roleFeatures.includes(feature.name) && (
                            <Check className="h-3 w-3" />
                          )}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium">
                            {feature.name.replace(/_/g, " ")}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {feature.description}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowRoleDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleSaveRole} disabled={!roleName}>
                {editingRole ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
}
