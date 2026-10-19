package com.github.macastrogimenez.embeddingProcessor;


import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.google.gson.Gson;

public class EmbeddingService {
        private static final String OLLAMA_URL =
                System.getenv().getOrDefault(
                        "OLLAMA_URL",
                        "http://localhost:11434"
                );

        private static final String MODEL = "nomic-embed-text";

        private final HttpClient client = HttpClient.newHttpClient();
        private final Gson gson = new Gson();

        public List<Double> embed (String text, boolean isQuery) throws Exception{
                // determine text-to-embed prefix
                String prefix = isQuery
                        ? "search_query: "
                        : "search_document: ";
                
                // Construct request body
                Map<String, String> body = Map.of(
                                "model", MODEL,
                                "input", prefix + text
                        );
                
                // parse body to JSON
                String json = gson.toJson(body);

                // construct http request
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(OLLAMA_URL + "/api/embed"))
                        .timeout(Duration.ofSeconds(60))
                        .header("Content-type", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(json))
                        .build();
                
                // send request
                HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
                
                // raise error if http response code is anything other than 200 (success)
                if(response.statusCode() != 200){
                        throw new RuntimeException(
                                "Ollama error: " + response.body()
                        );
                }

                EmbeddingResponse result = gson.fromJson(response.body(), EmbeddingResponse.class);

                if (result == null || result.embeddings() == null || result.embeddings().isEmpty()) {
                        throw new IllegalStateException("No embeddings returned");
                }

                return result.embeddings().get(0);
        }
}
