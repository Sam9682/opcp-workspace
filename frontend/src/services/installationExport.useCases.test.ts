import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./prerequisitesService", () => ({
  prerequisitesService: {
    loadClientAnswers: vi.fn(),
    loadCredentialConfig: vi.fn().mockRejectedValue(new Error("none")),
    loadServerNodes: vi.fn().mockResolvedValue({ nodes: [] }),
  },
}));

import { prerequisitesService } from "./prerequisitesService";
import {
  buildArchitectureDocumentHtml,
  buildInstallationExport,
} from "./installationExport";
import {
  CONTEXT_SLUG,
  isUseCaseDisabled,
} from "../components/prerequisites/checklistCategories";

const installation = { id: "inst-1", project_name: "Proj" } as Parameters<
  typeof buildInstallationExport
>[0];

const mockContext = (context: Record<string, string>) => {
  vi.mocked(prerequisitesService.loadClientAnswers).mockImplementation(
    async (_id, slug) => ({
      slug,
      answers: slug === CONTEXT_SLUG ? context : { [`${slug}-row`]: "v" },
    }),
  );
};

describe("OPCP Context use cases gate export + architecture document", () => {
  beforeEach(() =>
    vi.mocked(prerequisitesService.loadClientAnswers).mockReset(),
  );

  it("isUseCaseDisabled falls back to defaults (Yes) and maps legacy values", () => {
    expect(isUseCaseDisabled("cloudstore", {})).toBe(false);
    expect(isUseCaseDisabled("vcf", { "ctx-usecase-vcf": "No" })).toBe(true);
    expect(
      isUseCaseDisabled("vcf", { "ctx-usecase-vcf": "Out of Scope" }),
    ).toBe(true);
    expect(
      isUseCaseDisabled("vcf", { "ctx-usecase-vcf": "Within Scope" }),
    ).toBe(false);
    expect(
      isUseCaseDisabled("network-checklist", { "ctx-usecase-vcf": "No" }),
    ).toBe(false);
  });

  it("export skips CloudStore and VCF when their use case is No", async () => {
    mockContext({ "ctx-usecase-cloudstore": "No", "ctx-usecase-vcf": "No" });
    const data = await buildInstallationExport(installation);
    expect(Object.keys(data.tabs)).not.toContain("cloudstore");
    expect(Object.keys(data.tabs)).not.toContain("vcf");
    expect(Object.keys(data.tabs)).toContain("network-checklist");

    const html = buildArchitectureDocumentHtml(data);
    expect(html).not.toContain("<h2>CloudStore</h2>");
    expect(html).not.toContain("<li>CloudStore</li>");
    expect(html).not.toContain("<li>VCF</li>");
    expect(html).toContain("<li>Network Checklist</li>");
  });

  it("export keeps CloudStore and VCF when their use case is Yes", async () => {
    mockContext({ "ctx-usecase-cloudstore": "Yes", "ctx-usecase-vcf": "Yes" });
    const data = await buildInstallationExport(installation);
    expect(Object.keys(data.tabs)).toEqual(
      expect.arrayContaining(["cloudstore", "vcf"]),
    );
    const html = buildArchitectureDocumentHtml(data);
    expect(html).toContain("<li>CloudStore</li>");
    expect(html).toContain("<li>VCF</li>");
  });
});
