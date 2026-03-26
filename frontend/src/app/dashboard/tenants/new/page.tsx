"use client";

import { useState, Fragment } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Building2,
  Shield,
  Cpu,
  Bot,
  ClipboardList,
} from "lucide-react";
import type { ReactNode } from "react";
import { apiFetch } from "@/lib/api";

// --------------- Step Indicator ---------------
function StepIndicator({
  steps,
  currentStep,
}: {
  steps: { label: string; icon: ReactNode }[];
  currentStep: number;
}) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {steps.map((step, i) => (
        <Fragment key={i}>
          {i > 0 && (
            <div
              className={`h-px flex-1 ${
                i <= currentStep ? "bg-blue-600" : "bg-gray-200"
              }`}
            />
          )}
          <div className="flex flex-col items-center gap-1">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                i < currentStep
                  ? "bg-blue-600 text-white"
                  : i === currentStep
                    ? "border-2 border-blue-600 text-blue-600"
                    : "border-2 border-gray-300 text-gray-400"
              }`}
            >
              {i < currentStep ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            <span
              className={`text-xs ${
                i <= currentStep ? "text-gray-700" : "text-gray-400"
              }`}
            >
              {step.label}
            </span>
          </div>
        </Fragment>
      ))}
    </div>
  );
}

const STEPS = [
  { label: "Organization", icon: <Building2 className="h-4 w-4" /> },
  { label: "Entra ID", icon: <Shield className="h-4 w-4" /> },
  { label: "Model Endpoint", icon: <Cpu className="h-4 w-4" /> },
  { label: "First Agent", icon: <Bot className="h-4 w-4" /> },
  { label: "Review", icon: <ClipboardList className="h-4 w-4" /> },
];

export default function NewTenantPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);

  const [formData, setFormData] = useState({
    // Step 1 — Organization (required)
    name: "",
    slug: "",
    admin_email: "",
    // Step 2 — Entra ID (optional)
    entra_tenant_id: "",
    entra_group_id: "",
    // Step 3 — Model Endpoint (optional)
    endpoint_name: "",
    provider: "azure-openai",
    endpoint_url: "",
    model_name: "",
    api_version: "",
    // Step 4 — First Agent (optional)
    agent_name: "",
    agent_description: "",
    agent_system_prompt: "",
  });

  const update = (field: string, value: string) => {
    setFormData((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "name" && !slugEdited) {
        next.slug = value
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "");
      }
      return next;
    });
    if (field === "slug") setSlugEdited(true);
  };

  const step1Valid =
    formData.name.trim() !== "" &&
    formData.slug.trim() !== "" &&
    formData.admin_email.trim() !== "";

  const isOptionalStepFilled = (step: number) => {
    if (step === 1)
      return formData.entra_tenant_id !== "" || formData.entra_group_id !== "";
    if (step === 2)
      return formData.endpoint_name !== "" || formData.endpoint_url !== "";
    if (step === 3)
      return formData.agent_name !== "" || formData.agent_system_prompt !== "";
    return false;
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError("");
    try {
      const tenantRes = await apiFetch<{ id: string }>(
        "/api/v1/tenants",
        {
          method: "POST",
          body: JSON.stringify({
            name: formData.name,
            slug: formData.slug,
            admin_email: formData.admin_email,
          }),
        }
      );
      const tenantId = tenantRes.id;

      let endpointId: string | null = null;
      if (
        formData.endpoint_name &&
        formData.endpoint_url &&
        formData.model_name
      ) {
        const endpointRes = await apiFetch<{ id: string }>(
          "/api/v1/model-endpoints",
          {
            method: "POST",
            body: JSON.stringify({
              name: formData.endpoint_name,
              provider: formData.provider,
              endpoint_url: formData.endpoint_url,
              model_name: formData.model_name,
              api_version: formData.api_version || undefined,
              tenant_id: tenantId,
            }),
          }
        );
        endpointId = endpointRes.id;
      }

      if (formData.agent_name && formData.agent_system_prompt && endpointId) {
        await apiFetch("/api/v1/agents", {
          method: "POST",
          body: JSON.stringify({
            name: formData.agent_name,
            description: formData.agent_description || undefined,
            system_prompt: formData.agent_system_prompt,
            model_endpoint_id: endpointId,
            tenant_id: tenantId,
          }),
        });
      }

      router.push(`/dashboard/tenants/${tenantId}`);
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to create tenant"
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">New Tenant</h1>
      <p className="text-sm text-gray-500 mb-6">
        Set up a new tenant in 5 steps. Only the first step is required.
      </p>

      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {/* Step 1 — Organization */}
      {currentStep === 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Organization Details
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Set up the basic tenant information.
          </p>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">
              Tenant Name *
            </span>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => update("name", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="Acme Corp"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Slug *</span>
            <input
              type="text"
              value={formData.slug}
              onChange={(e) => update("slug", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="acme-corp"
            />
            <p className="text-xs text-gray-400 mt-1">
              URL-safe identifier. Auto-generated from name.
            </p>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">
              Admin Email *
            </span>
            <input
              type="email"
              value={formData.admin_email}
              onChange={(e) => update("admin_email", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="admin@acme.com"
            />
          </label>
        </div>
      )}

      {/* Step 2 — Entra ID */}
      {currentStep === 1 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Entra ID Configuration
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Optional. Connect to Microsoft Entra ID for SSO and group-based
            access.
          </p>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">
              Entra Tenant ID
            </span>
            <input
              type="text"
              value={formData.entra_tenant_id}
              onChange={(e) => update("entra_tenant_id", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">
              Entra Group ID
            </span>
            <input
              type="text"
              value={formData.entra_group_id}
              onChange={(e) => update("entra_group_id", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            />
          </label>
          <div className="rounded-md bg-gray-50 p-4 text-sm text-gray-600 mt-4">
            You can configure this later from the tenant settings.
          </div>
        </div>
      )}

      {/* Step 3 — Model Endpoint */}
      {currentStep === 2 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Model Endpoint
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Optional. Set up an AI model endpoint for this tenant&apos;s agents.
          </p>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">
              Endpoint Name
            </span>
            <input
              type="text"
              value={formData.endpoint_name}
              onChange={(e) => update("endpoint_name", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="GPT-4o Production"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">Provider</span>
            <select
              value={formData.provider}
              onChange={(e) => update("provider", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            >
              <option value="azure-openai">Azure OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">
              Endpoint URL
            </span>
            <input
              type="text"
              value={formData.endpoint_url}
              onChange={(e) => update("endpoint_url", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="https://my-resource.openai.azure.com"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-gray-700">
              Model Name
            </span>
            <input
              type="text"
              value={formData.model_name}
              onChange={(e) => update("model_name", e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="gpt-4o"
            />
          </label>
          {formData.provider === "azure-openai" && (
            <label className="block">
              <span className="text-sm font-medium text-gray-700">
                API Version
              </span>
              <input
                type="text"
                value={formData.api_version}
                onChange={(e) => update("api_version", e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                placeholder="2024-06-01"
              />
            </label>
          )}
          <div className="rounded-md bg-gray-50 p-4 text-sm text-gray-600 mt-4">
            You can configure this later from the tenant settings.
          </div>
        </div>
      )}

      {/* Step 4 — First Agent */}
      {currentStep === 3 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">First Agent</h2>
          <p className="text-sm text-gray-500 mb-4">
            Optional. Create the first agent for this tenant. Requires a model
            endpoint from the previous step.
          </p>
          {!formData.endpoint_name ? (
            <div className="rounded-md bg-yellow-50 p-4 text-sm text-yellow-700">
              Set up a model endpoint first (Step 3) to create an agent, or skip
              this step.
            </div>
          ) : (
            <>
              <label className="block">
                <span className="text-sm font-medium text-gray-700">
                  Agent Name
                </span>
                <input
                  type="text"
                  value={formData.agent_name}
                  onChange={(e) => update("agent_name", e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="Support Agent"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700">
                  Description
                </span>
                <input
                  type="text"
                  value={formData.agent_description}
                  onChange={(e) => update("agent_description", e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="Handles customer support queries"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700">
                  System Prompt
                </span>
                <textarea
                  rows={4}
                  value={formData.agent_system_prompt}
                  onChange={(e) =>
                    update("agent_system_prompt", e.target.value)
                  }
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="You are a helpful assistant..."
                />
              </label>
            </>
          )}
        </div>
      )}

      {/* Step 5 — Review */}
      {currentStep === 4 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Review &amp; Create
          </h2>
          <div className="rounded-lg border border-gray-200 bg-white p-6 space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-500">
                Organization
              </h3>
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-gray-500">Name</dt>
                <dd className="text-gray-900">{formData.name}</dd>
                <dt className="text-gray-500">Slug</dt>
                <dd className="text-gray-900">{formData.slug}</dd>
                <dt className="text-gray-500">Admin Email</dt>
                <dd className="text-gray-900">{formData.admin_email}</dd>
              </dl>
            </div>

            {(formData.entra_tenant_id || formData.entra_group_id) && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Entra ID</h3>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {formData.entra_tenant_id && (
                    <>
                      <dt className="text-gray-500">Tenant ID</dt>
                      <dd className="text-gray-900">
                        {formData.entra_tenant_id}
                      </dd>
                    </>
                  )}
                  {formData.entra_group_id && (
                    <>
                      <dt className="text-gray-500">Group ID</dt>
                      <dd className="text-gray-900">
                        {formData.entra_group_id}
                      </dd>
                    </>
                  )}
                </dl>
              </div>
            )}

            {(formData.endpoint_name || formData.endpoint_url) && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">
                  Model Endpoint
                </h3>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <dt className="text-gray-500">Name</dt>
                  <dd className="text-gray-900">{formData.endpoint_name}</dd>
                  <dt className="text-gray-500">Provider</dt>
                  <dd className="text-gray-900">{formData.provider}</dd>
                  <dt className="text-gray-500">URL</dt>
                  <dd className="text-gray-900">{formData.endpoint_url}</dd>
                  <dt className="text-gray-500">Model</dt>
                  <dd className="text-gray-900">{formData.model_name}</dd>
                </dl>
              </div>
            )}

            {formData.agent_name && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">
                  First Agent
                </h3>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <dt className="text-gray-500">Name</dt>
                  <dd className="text-gray-900">{formData.agent_name}</dd>
                  {formData.agent_description && (
                    <>
                      <dt className="text-gray-500">Description</dt>
                      <dd className="text-gray-900">
                        {formData.agent_description}
                      </dd>
                    </>
                  )}
                </dl>
              </div>
            )}
          </div>

          {submitError && (
            <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
              {submitError}
            </div>
          )}
        </div>
      )}

      {/* Navigation footer */}
      <div className="flex justify-between mt-8 pt-6 border-t border-gray-200">
        {currentStep > 0 ? (
          <button
            onClick={() => setCurrentStep((s) => s - 1)}
            className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
        ) : (
          <Link
            href="/dashboard/tenants"
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4" /> Cancel
          </Link>
        )}

        {currentStep < 4 ? (
          <button
            onClick={() => setCurrentStep((s) => s + 1)}
            disabled={currentStep === 0 && !step1Valid}
            className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {currentStep >= 1 && currentStep <= 3 && !isOptionalStepFilled(currentStep)
              ? "Skip"
              : "Next"}{" "}
            <ArrowRight className="h-4 w-4" />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create Tenant"}
          </button>
        )}
      </div>
    </div>
  );
}
