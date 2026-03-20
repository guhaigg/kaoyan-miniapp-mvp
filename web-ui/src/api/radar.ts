import { request, type RadarPredictRequest, type RadarPredictResponse } from "@/lib/api";

export const predictRadar = (payload: RadarPredictRequest) =>
  request<RadarPredictResponse>({
    method: "POST",
    url: "/radar/predict",
    data: payload,
    timeout: 30_000,
  });
