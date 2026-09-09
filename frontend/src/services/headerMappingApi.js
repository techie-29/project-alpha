const API_BASE_URL = "http://localhost:5000";

export async function runHeaderMapping(ingestionId) {
  const token = localStorage.getItem("alphaToken");

  const response = await fetch(
    `${API_BASE_URL}/api/header-mapping/${ingestionId}`,
    {
      method: "POST",

      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.message || "Header mapping failed"
    );  
  }

  return data;
}