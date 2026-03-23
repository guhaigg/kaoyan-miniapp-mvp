import { api, type SchoolSuggestResponse } from "@/lib/api";

export const fetchSchoolSuggestions = (params?: {
  q?: string;
  limit?: number;
}) => api.get<SchoolSuggestResponse>("/schools/suggest", { params }).then((response) => response.data);
