package com.github.macastrogimenez.embeddingProcessor;

import com.google.gson.Gson;
import com.google.gson.JsonObject;

import io.milvus.v2.client.ConnectConfig;
import io.milvus.v2.client.MilvusClientV2;
import io.milvus.v2.common.ConsistencyLevel;
import io.milvus.v2.common.DataType;
import io.milvus.v2.common.IndexParam;
import io.milvus.v2.common.IndexParam.IndexParamBuilder;
import io.milvus.v2.service.collection.request.AddFieldReq;
import io.milvus.v2.service.collection.request.CreateCollectionReq;
import io.milvus.v2.service.collection.request.DescribeCollectionReq;
import io.milvus.v2.service.collection.request.GetLoadStateReq;
import io.milvus.v2.service.collection.request.HasCollectionReq;
import io.milvus.v2.service.collection.request.LoadCollectionReq;
import io.milvus.v2.service.collection.response.DescribeCollectionResp;
import io.milvus.v2.service.vector.request.QueryReq;
import io.milvus.v2.service.vector.request.SearchReq;
import io.milvus.v2.service.vector.request.UpsertReq;
import io.milvus.v2.service.vector.request.data.FloatVec;
import io.milvus.v2.service.vector.response.QueryResp;
import io.milvus.v2.service.vector.response.SearchResp;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.List;

public class MilvusRepository implements AutoCloseable {
    
    private static final String COLLECTION = "academic_documents";
    private static final int DIMENSIONS = 768;
    private final MilvusClientV2 client;
    private final Gson gson = new Gson();

    public MilvusRepository (){
        String uri = System.getenv().getOrDefault(
            "MILVUS_URL", "http://localhost:19530"
        );

        String token = System.getenv().getOrDefault("MILVUS_TOKEN", "root:Milvus");

        
        client = new MilvusClientV2(
            ConnectConfig.builder()
                .uri(uri)
                .token(token)
                .build()
        );
    }

    public void initializeCollection(){
        boolean exists = client.hasCollection(
            HasCollectionReq.builder()
                .collectionName(COLLECTION)
                .build()   
        );

        if (exists == false){
            CreateCollectionReq.CollectionSchema schema = CreateCollectionReq.CollectionSchema.builder().build();
            schema.addField(
                AddFieldReq.builder()
                .fieldName("id")
                .isPrimaryKey(true)
                .maxLength(256)
                .dataType(DataType.VarChar)
                .autoID(false)
                .build()
            );

            schema.addField(
                AddFieldReq.builder()
                .fieldName("document_id")
                .maxLength(256)
                .dataType(DataType.VarChar)
                .autoID(false)
                .build()
            );

            schema.addField(
                AddFieldReq.builder()
                .fieldName("document_type")
                .dataType(DataType.VarChar)
                .maxLength(32)
                .build()
            );

            schema.addField(
                AddFieldReq.builder()
                .fieldName("embeddings")
                .dataType(DataType.FloatVector)
                .dimension(DIMENSIONS)
                .build()
            );

            IndexParam index = IndexParam.builder()
                .fieldName("embeddings")
                .indexType(IndexParam.IndexType.AUTOINDEX)
                .metricType(IndexParam.MetricType.COSINE)
                .build();

            client.createCollection(
                CreateCollectionReq.builder()
                .collectionName(COLLECTION)
                .collectionSchema(schema)
                .indexParams(List.of(index))
                .build()
            );

            System.out.printf("Created the collection: %s", COLLECTION);
        }

        boolean loaded = client.getLoadState(
            GetLoadStateReq.builder()
            .collectionName(COLLECTION)
            .build()
        );

        if (loaded == false) {
            client.loadCollection(
                LoadCollectionReq.builder()
                    .collectionName(COLLECTION)
                    .build()
            );
        }
    }
    
    private float[] toFloatArray (List<Double> embedding){
        if (embedding == null || embedding.size() != DIMENSIONS){
            throw new IllegalArgumentException(
                "The embedding does not have 758 Dimensions"
            );
        }

        float[] vector = new float[DIMENSIONS];
        boolean nonZero = false;

        for (int i = 0; i < DIMENSIONS; i++) {
            Double value = embedding.get(i);
            if (value == null || !Double.isFinite(value)){
                throw new IllegalArgumentException(
                    "Invalid embedding value"
                );
            }
            vector[i] = value.floatValue();

            if (Float.isFinite(vector[i])==false){
                throw new IllegalArgumentException(
                    "Embedding value exceeds Float range"
                );
            }

            if (vector[i]!= 0){
                nonZero = true;
            }
        }

        if(!nonZero){
            throw new IllegalArgumentException(
                "Embedding cannot be zero"
            );
        }

        return vector;
    }

    @Override 
    public void close(){
        client.close();
    }

    public void saveBatch(List<VectorDocument> documents){
        if (documents.isEmpty()){
            return;
        }

        // 1. create rows array List
        ArrayList<JsonObject> rows = new ArrayList<>();

        // 2. foreach to loop over all documents
        for (VectorDocument document : documents) {
            // 3. extract doc type and doc id
            String docType = document.getDocumentType();
            String docId = document.getDocumentId();

            // 4. check for null doc id, blank doc id, length longer than 256 and length of doc id + doc type shorter than 256
            if(
                docId == null ||
                docId.isBlank() ||
                docId.length() > 256 ||
                (docId + docType).length() > 256
            ){
                // throw error if yes
                throw new IllegalArgumentException(
                    "docId or docType are invalid"
                );
            }

            // 5. create json Object as row
            JsonObject row = new JsonObject();

            // 6. add to json object id: doctype + : + docID
            row.addProperty("id", docType+":"+docId);
            // 7. add to json object doctype
            row.addProperty("document_type", docType);
            row.addProperty("document_id", docId);
            // 8. add to json object docID

            // 10. add embeddings to json 
            row.add(
                "embeddings",
                // 9. convert embeddings to float
                gson.toJsonTree(toFloatArray(document.getEmbedding()))
            );

            // 11. add to rows array list
            rows.add(row);
        }
        // 12. client upsert rows 
        client.upsert(
            UpsertReq.builder()
                .collectionName(COLLECTION)
                .data(rows)
                .build()   
        );

        System.out.printf("%d documents have been inserted in Milvus collection: %s", documents.size(), COLLECTION);
        // 13. if success return docs inserted
    }

    public List<VectorSearchResult> searchKNN(List<Double> queryEmbedding, int topK){
        // 1. check topK is positive else return error
        if (topK<1){
            throw new IllegalArgumentException(
                "Top k must be a positive number"
            );
        }

        // 2. turn the vector from list of double to array of float
        FloatVec qE = new FloatVec(toFloatArray(queryEmbedding));

        // 3. construct response using SearchResp
        SearchResp response = client.search(
            SearchReq.builder()
            .collectionName(COLLECTION)
            .annsField("embeddings")
            .data(List.of(qE))
            .limit(topK)
            .outputFields(
                List.of(
                    "document_type",
                    "document_id"
                )
            )
            .consistencyLevel(ConsistencyLevel.STRONG)
            .build()
        );
            
        // 4. create List of VectorSearchResult object
        List<VectorSearchResult> results = new ArrayList<>();

        
        // 5. copy results with foreach to new list object
        // get metadata
        // extract doc type and doc id
        // get score 

        // Milvus allows to search for more than a single query, therefore its search results are a list of lists, if we are only checking for searching for 
        // kNN to a single query, then we can access the first list in the list of lists
        for (SearchResp.SearchResult sr : response.getSearchResults().get(0)) {
            Map<String,Object> metadata = sr.getEntity();

            String docType = metadata.get("document_type").toString();
            String docId = metadata.get("document_id").toString();
            float score = sr.getScore();

            VectorSearchResult vr = new VectorSearchResult(docType, docId, score);
            results.add(vr);
        }
        // 6. return list object
        return  results;
    }

}
