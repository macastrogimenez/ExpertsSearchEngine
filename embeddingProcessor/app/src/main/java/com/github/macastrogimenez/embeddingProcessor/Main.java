package com.github.macastrogimenez.embeddingProcessor;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Arrays;
import java.sql.Array;
import java.util.List;

import org.springframework.boot.SpringApplication;
public class Main 
    {
        public static void main(String[] args) throws Exception {

            String host = System.getenv("DB_HOST");
            String database = System.getenv("DB_NAME");
            String username = System.getenv("DB_USERNAME");
            String password = System.getenv("DB_PASSWORD");
            String url =
                    "jdbc:aws-wrapper:postgresql://" +
                    host +
                    ":5432/" +
                    database;
            if (args.length == 0) {
                throw new IllegalArgumentException(
                    "Expected a mode: search or embeddingGen"
                );
            }
            String mode = args[0];
            if (mode.equals("search")){
                SpringApplication.run(SearchApplication.class);
            }
            else if (mode.equals("embeddingGen"))
            {
                try(
                    MilvusRepository milvusRepository = new MilvusRepository(false)
                ){
                    milvusRepository.initializeCollection();
    
                    // following 5 lines connect to the DB    
                    try (Connection connection =
                                DriverManager.getConnection(
                                        url,
                                        username,
                                        password)) 
                        {
                            System.out.println("Connected!");
                            
                            // Vectorise courses
                            try(
                                    Statement statement = connection.createStatement(ResultSet.TYPE_SCROLL_INSENSITIVE, ResultSet.CONCUR_READ_ONLY);
                                    ResultSet resultCourses = statement.executeQuery(
                                        """ 
                                        SELECT 
                                            c.id,
                                            c.title,
                                            c.abstract,
                                            c.description,
                                            p.uuid
                                        FROM prod.course_contributor AS CC
                                        LEFT JOIN prod.person AS p
                                            ON p.uuid = cc.person_uuid
                                        LEFT JOIN prod.course AS c
                                            ON c.id = cc.course_id
                                            ;
                                        """);
                                )
                            {
                                resultCourses.last();
                                int setSize = resultCourses.getRow();
                                VectorDocument[] searchCourses = new VectorDocument[setSize+1];
                                
                                int rowCount = 0;
                                ArrayList<String> hundredCourseEmbeddingText = new ArrayList<>();
                                EmbeddingService embeddingService = new EmbeddingService();
                                resultCourses.beforeFirst();
                                while(resultCourses.next()) {
                                    rowCount++;
                                    StringBuilder courseEmbeddingText = new StringBuilder();
        
                                    String courseId = resultCourses.getString(1);
                                    String courseTitle = resultCourses.getString(2);
                                    String courseAbstract = resultCourses.getString(3);
                                    String courseDescription = resultCourses.getString(4);
                                    String courseProfessor = resultCourses.getString(5);

                                    List<String> contrList = new ArrayList<>();
                                    contrList.add(courseProfessor);
                                    
                                    courseEmbeddingText.append(
                                        "search_document: "+ "\n" +
                                        "title: " + courseTitle
                                        + "\n"
                                        + "abstract: " + courseAbstract
                                        + "\n"
                                        + "description: " + courseDescription
                                    );
                                    
                                    hundredCourseEmbeddingText.add(courseEmbeddingText.toString());
                                        
                                    //SearchCourse c = new SearchCourse(courseId, courseTitle, courseAbstract, courseDescription, courseProgramme, courseProfessor);
                                    //searchCourses.put(rowCount, c);
        
                                    VectorDocument d = new VectorDocument("course", courseId, contrList);
                                    searchCourses[rowCount] = d;
        
                                    if (hundredCourseEmbeddingText.size() == 100) {
                                        embedCourseBatch(embeddingService, hundredCourseEmbeddingText, searchCourses, rowCount, milvusRepository);
                                    }
        
                                }
                                embedCourseBatch(embeddingService, hundredCourseEmbeddingText, searchCourses, rowCount, milvusRepository);
                                hundredCourseEmbeddingText.clear();
                                searchCourses = null;
                            }
        
                            try (
                                    Statement statement = connection.createStatement(ResultSet.TYPE_SCROLL_INSENSITIVE, ResultSet.CONCUR_READ_ONLY);
                                    ResultSet resultPapers = statement.executeQuery(
                                    // this query returns papers and their contributors in an array - if a paper has no contributors it is left out
                                        """
                                            SELECT
                                                p.uuid,
                                                p.title,
                                                p.subtitle,
                                                p.abstract,
                                                ARRAY_AGG(pc.person_uuid) FILTER (
                                                    WHERE pc.person_uuid IS NOT NULL
                                                ) AS contributors
                                            FROM prod.paper p
                                            LEFT JOIN prod.paper_contributors pc
                                                ON pc.paper_uuid = p.uuid
                                            GROUP BY p.uuid
                                            HAVING COUNT(pc.person_uuid) > 0;
                                        """
                                    )
                            ) 
                            {
                                resultPapers.last();
                                int setSize = resultPapers.getRow();
                                VectorDocument[] searchPapers = new VectorDocument[setSize + 1];
                                resultPapers.beforeFirst();
                                int rowCount = 0;
                                ArrayList<String> hundredPapersdocStrings = new ArrayList<>();
                                EmbeddingService embeddingService = new EmbeddingService();
                                while (resultPapers.next()){
                                    rowCount++;
                                    StringBuilder s = new StringBuilder();
        
                                    String uuid = resultPapers.getString(1);
                                    // String year = resultPapers.getString(2);
                                    // String paperType = resultPapers.getString(3);
                                    String title = resultPapers.getString(2);
                                    String subtitle = resultPapers.getString(3);
                                    String paperAbstract = resultPapers.getString(4);
                                    Array sqlContributors = resultPapers.getArray(5);
        
                                    List<String> contrList = new ArrayList<>();
                                    if (sqlContributors != null){
                                        try{
                                            Object[] values = (Object[]) sqlContributors.getArray();
                                            contrList = Arrays.stream(values).map((Object v) -> v.toString()).toList();
                                        } finally{
                                            sqlContributors.free();
                                        }
                                    }
                                                
                                    s.append(
                                        "search_document: "+ "\n" +
                                        "title: " + title
                                        + "\n"
                                        + "subtitle: " + subtitle
                                        + "\n"
                                        + "abstract: " + paperAbstract
                                    );
        
                                    hundredPapersdocStrings.add(s.toString());
                                    VectorDocument sp = new VectorDocument("paper", uuid, contrList);
                                    searchPapers[rowCount] = sp;
        
                                    if (hundredPapersdocStrings.size() == 100){
                                        embedPaperBatch(embeddingService, hundredPapersdocStrings, searchPapers, rowCount, milvusRepository);
                                    }
                                    
                                }
                                embedPaperBatch(embeddingService, hundredPapersdocStrings, searchPapers, rowCount, milvusRepository);
                                hundredPapersdocStrings.clear();
                                searchPapers = null;
                            }
                            try(
                                Statement statement = connection.createStatement(ResultSet.TYPE_SCROLL_INSENSITIVE, ResultSet.CONCUR_READ_ONLY);
                                ResultSet resultProjects = statement.executeQuery(
                                    // aggregates participants and only shows projects that have more than 0 participants.
                                    """
                                        SELECT 
                                            pj.uuid, 
                                            pj.title, 
                                            pj.description,
                                            ARRAY_AGG(pp.person_uuid) FILTER (
                                                WHERE pp.person_uuid iS NOT NULL
                                                ) AS participants
                                        FROM prod.project pj
                                        LEFT JOIN prod.project_participants pp
                                            ON pp.project_uuid = pj.uuid 
                                        GROUP BY 1,2,3
                                        HAVING COUNT (pp.person_uuid) > 0
                                        ;
                                    """
                                )
                            ){
                                resultProjects.last();
                                int setSize = resultProjects.getRow();
                                VectorDocument[] searchProjects = new VectorDocument[setSize + 1];
                                resultProjects.beforeFirst();
                                int rowCount = 0;
                                ArrayList<String> hundredProjectsdocStrings = new ArrayList<>();
                                EmbeddingService embeddingService = new EmbeddingService();
        
                                while (resultProjects.next()) {
                                    rowCount++;
        
                                    String uuid = resultProjects.getString(1);
                                    String title = resultProjects.getString(2);
                                    String description = resultProjects.getString(3);
                                    Array sqlParticipants = resultProjects.getArray(4);
                                    List<String> participants = new ArrayList<>();
        
                                    if (sqlParticipants != null){
                                        try {
                                                participants = Arrays.stream((Object[])sqlParticipants.getArray()).map((Object v) -> v.toString()).toList();
                                            }
                                        finally {
                                            
                                            sqlParticipants.free();
                                        }
                                    }
        
                                    StringBuilder s = new StringBuilder();
        
                                    s.append(
                                        "search_document: "+ "\n" +
                                        "title: " + title
                                        + "\n"
                                        + "description: " + description
                                    );
        
                                    hundredProjectsdocStrings.add(s.toString());
                                    //SearchProject p = new SearchProject(uuid, title, description, participants);
                                    VectorDocument p = new VectorDocument("project", uuid, participants);
                                    searchProjects[rowCount] = p;
        
                                    if(hundredProjectsdocStrings.size()==100){
                                        embedProjectBatch(embeddingService, hundredProjectsdocStrings, searchProjects, rowCount, milvusRepository);
                                    }
                                }
                                embedProjectBatch(embeddingService, hundredProjectsdocStrings, searchProjects, rowCount, milvusRepository);
                                hundredProjectsdocStrings.clear();
                                searchProjects = null;
                            }
                        }
                    }
            }
        }
                    

        static void embedCourseBatch
            (
                EmbeddingService service, 
                ArrayList<String> texts,
                VectorDocument[] searchCourses,
                int rowCount,
                MilvusRepository milvusRepository
            ) throws Exception {
                if (texts.isEmpty()) {
                    return;
                }
                // select only the relevant search courses
                VectorDocument[] scCopy = Arrays.copyOfRange(
                    searchCourses,
                    rowCount - texts.size() + 1,
                    rowCount + 1
                );
                
                // generate embeddings for all texts
                List<List<Double>> embeddings = service.batchEmbed(texts);
                
                //check correct size of embeddings list
                if (embeddings.size() != texts.size()) {
                    throw new IllegalStateException("Expected " + texts.size()
                    + " embeddings, received " + embeddings.size());
                }
                
                int i = 0;
                for (List<Double> docVector : embeddings) {
                    scCopy[i].setEmbedding(docVector);
                    i++;     
                }
                
                // turn array into list
                List<VectorDocument> spList = Arrays.asList(scCopy); 
                    
                //saving all VectorDocuments to Milvus vector db  here and clear searchCourses
                milvusRepository.saveBatch(spList);
                spList = null;
                embeddings = null;
                texts.clear();
                System.out.printf("\nCourse rows processed: %d%n", rowCount);
            }

        static void embedPaperBatch
            (
                EmbeddingService service, 
                ArrayList<String> texts,
                VectorDocument[] searchPapers,
                int rowCount,
                MilvusRepository milvusRepository
            ) throws Exception {
                if (texts.isEmpty()) {
                    return;
                }
                VectorDocument[] batchPapers = Arrays.copyOfRange(
                    searchPapers,
                    rowCount - texts.size() + 1,
                    rowCount + 1
                );
                List<List<Double>> embeddings = service.batchEmbed(texts);
                if (embeddings.size() != texts.size()) {
                    throw new IllegalStateException("Expected " + texts.size()
                            + " embeddings, received " + embeddings.size());
                }
                for (int i = 0; i < texts.size(); i++) {
                    batchPapers[i].setEmbedding(embeddings.get(i));
                }
                // Save only the documents in this batch.
                milvusRepository.saveBatch(Arrays.asList(batchPapers));

                texts.clear();
                System.out.printf("\nPaper rows processed: %d%n", rowCount);
            }
            
            static void embedProjectBatch
            (
                EmbeddingService service, 
                ArrayList<String> texts,
                VectorDocument[] searchProjects,
                int rowCount,
                MilvusRepository milvusRepository
            ) throws Exception {
                if (texts.isEmpty()) {
                    return;
                }
                VectorDocument[] batchProjects = Arrays.copyOfRange(
                    searchProjects,
                    rowCount - texts.size() + 1,
                    rowCount + 1
                );
                List<List<Double>> embeddings = service.batchEmbed(texts);
                if (embeddings.size() != texts.size()) {
                    throw new IllegalStateException("Expected " + texts.size()
                            + " embeddings, received " + embeddings.size());
                }
                for (int i = 0; i < texts.size(); i++) {
                    batchProjects[i].setEmbedding(embeddings.get(i));
                }
                // Save only the documents in this batch.
                milvusRepository.saveBatch(Arrays.asList(batchProjects));

                texts.clear();
                System.out.printf("\nProject rows processed: %d%n", rowCount);
            }


    }
