package com.github.macastrogimenez.embeddingProcessor;

import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.server.ResponseStatusException;


@RestController 
public class SemanticSearchController {
    
    private final EmbeddingService embeddingService;
    private final MilvusRepository milvusRepository;

    public SemanticSearchController(
        EmbeddingService embeddingService,
        MilvusRepository milvusRepository
    ) {
        this.embeddingService = embeddingService;
        this.milvusRepository = milvusRepository;
    }

    @GetMapping("/semanticSearchFiltered")
    public List<VectorSearchResult> semanticSearchFiltered(
        @RequestParam("query") String query,
        @RequestParam ("K") int k,
        @RequestParam ("filter") String filter
    ) throws Exception {
        String[] validFilter = {"paper","course","project"};
        if (query.isBlank()){
            String error = "Query cannot be blank";
            System.out.println(error);
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Query cannot be blank");
        }
        if (k<1 || k>100){
            String error = "K needs to be between 1 and 100";
            System.out.println(error);
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,error);
        }
        if (Arrays.stream(validFilter).anyMatch((item) -> item.equals(filter))==false){
            String error = "The filter value must be either 'paper','project' or 'course'";
            System.out.println(error);
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, error);
        }
        else try {
            List<Double> embedding = embeddingService.embed(query, false);
            List<VectorSearchResult> searchResults = milvusRepository.searchFilter(embedding, k,filter);
            return searchResults;
        } catch (Exception e) {
            throw new Exception(e);
        }
    }

    @GetMapping("/semanticSearch")
    public List<VectorSearchResult> semanticSearch(
        @RequestParam("query") String query,
        @RequestParam ("K") int k
    ) throws Exception {
            if (query.isBlank()){
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Query cannot be blank");
            }
            if (k<1 || k>100){
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"K needs to be between 1 and 100");
            }
            else try {
                List<Double> embedding = embeddingService.embed(query, false);
                List<VectorSearchResult> searchResults = milvusRepository.searchKNN(embedding, k);
                return searchResults;
            } catch (Exception e) {
                throw new Exception(e);
            }
    }
    
}
