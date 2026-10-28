package com.github.macastrogimenez.embeddingProcessor;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.sql.Array;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
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
                            Statement statement = connection.createStatement();
                            ResultSet resultCourses = statement.executeQuery(
                                """ 
                                SELECT 
                                    c.id,
                                    c.title,
                                    c.abstract,
                                    c.description,
                                    c.programme,
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
                        int rowCount = 0;
                        HashMap<Integer, SearchCourse> searchCourses = new HashMap<>();
                        ArrayList<String> hundredCourseEmbeddingText = new ArrayList<>();
                        EmbeddingService embeddingService = new EmbeddingService();
                        while(resultCourses.next()) {
                            rowCount++;
                            StringBuilder courseEmbeddingText = new StringBuilder();

                            int courseId = Integer.parseInt(resultCourses.getString(1));
                            String courseTitle = resultCourses.getString(2);
                            String courseAbstract = resultCourses.getString(3);
                            String courseDescription = resultCourses.getString(4);
                            String courseProgramme = resultCourses.getString(5);
                            String courseProfessor = resultCourses.getString(6);
                            
                            courseEmbeddingText.append(
                                "search_document: "+ "\n" +
                                "title: " + courseTitle
                                + "\n"
                                + "abstract: " + courseAbstract
                                + "\n"
                                + "description: " + courseDescription
                            );
                            
                            hundredCourseEmbeddingText.add(courseEmbeddingText.toString());
                                
                            SearchCourse c = new SearchCourse(courseId, courseTitle, courseAbstract, courseDescription, courseProgramme, courseProfessor);
                            searchCourses.put(rowCount, c);
                            if (hundredCourseEmbeddingText.size() == 100) {
                                embedCourseBatch(embeddingService, hundredCourseEmbeddingText, searchCourses, rowCount);
                            }

                        }
                        embedCourseBatch(embeddingService, hundredCourseEmbeddingText, searchCourses, rowCount);
                        
                        //TODO [KAN-106]: Pass courses onto FAISS. At this stage, the HashMap searchCourses has the courses and corresponding embedding saved. Next thing would be to pass them on to FAISS. 
                    }

                    try (
                            Statement statement = connection.createStatement();
                            ResultSet resultPapers = statement.executeQuery(
                                """
                                    SELECT
                                        p.uuid,
                                        p.year,
                                        p.type,
                                        p.title,
                                        p.subtitle,
                                        p.abstract,
                                        ARRAY_AGG(pc.person_uuid) FILTER (
                                            WHERE pc.person_uuid IS NOT NULL
                                        ) AS contributors
                                    FROM prod.paper p
                                    LEFT JOIN prod.paper_contributors pc
                                        ON pc.paper_uuid = p.uuid
                                    GROUP BY
                                        p.uuid,
                                        p.year,
                                        p.type,
                                        p.title,
                                        p.subtitle,
                                        p.abstract;
                                """
                            )
                    ) 
                    {
                        int rowCount = 0;
                        HashMap<Integer, SearchPaper> searchPapers = new HashMap<>();
                        ArrayList<String> hundredPapersdocStrings = new ArrayList<>();
                        EmbeddingService embeddingService = new EmbeddingService();
                        while (resultPapers.next()){
                            rowCount++;
                            StringBuilder s = new StringBuilder();

                            String uuid = resultPapers.getString(1);
                            String year = resultPapers.getString(2);
                            String paperType = resultPapers.getString(3);
                            String title = resultPapers.getString(4);
                            String subtitle = resultPapers.getString(5);
                            String paperAbstract = resultPapers.getString(6);
                            Array sqlContributors = resultPapers.getArray(7);

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
                            SearchPaper sp = new SearchPaper(uuid, Integer.parseInt(year), paperType, title, subtitle, paperAbstract, contrList);
                            searchPapers.put(rowCount, sp);

                            if (hundredPapersdocStrings.size() == 100){
                                embedPaperBatch(embeddingService, hundredPapersdocStrings, searchPapers, rowCount);
                            }
                            //TODO [KAN-109]: Pass papers onto FAISS. At this stage, the HashMap searchPapers has the papers and corresponding embedding saved. Next thing would be to pass them on to FAISS. 
                            
                        }
                        embedPaperBatch(embeddingService, hundredPapersdocStrings, searchPapers, rowCount);
                    }
                    try(
                        Statement statement = connection.createStatement();
                        ResultSet resultProjects = statement.executeQuery(
                            """
                                SELECT 
                                    pj.uuid, 
                                    pj.title, 
                                    pj.description, 
                                    ARRAY_AGG(pjp.person_uuid) FILTER (
                                        WHERE pjp.person_uuid IS NOT NULL
                                    ) AS participants
                                FROM prod.project pj
                                LEFT JOIN prod.project_participants pjp ON
                                    pj.uuid = pjp.project_uuid
                                GROUP BY 
                                    pj.uuid, 
                                    pj.title, 
                                    pj.description
                                ;
                            """
                        )
                    ){
                        int rowCount = 0;
                        HashMap<Integer, SearchProject> searchProjects = new HashMap<>();
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
                            SearchProject p = new SearchProject(uuid, title, description, participants);
                            searchProjects.put(rowCount, p);

                            if(hundredProjectsdocStrings.size()==100){
                                embedProjectBatch(embeddingService, hundredProjectsdocStrings, searchProjects, rowCount);
                            }
                        }
                        embedProjectBatch(embeddingService, hundredProjectsdocStrings, searchProjects, rowCount);
                    }
                    //TODO [KAN-110]: Pass projects onto FAISS. At this stage, the HashMap searchProjects has the projects and corresponding embedding saved. Next thing would be to pass them on to FAISS. 
                }
            }

        static void embedCourseBatch
            (
                EmbeddingService service, 
                ArrayList<String> texts,
                HashMap<Integer, SearchCourse> searchCourses,
                int rowCount
            ) throws Exception {
                if (texts.isEmpty()) {
                    return;
                }
                List<List<Double>> embeddings = service.batchEmbed(texts);
                if (embeddings.size() != texts.size()) {
                    throw new IllegalStateException("Expected " + texts.size()
                            + " embeddings, received " + embeddings.size());
                }
                int firstKey = rowCount - texts.size() + 1;
                for (int i = 0; i < texts.size(); i++) {
                    searchCourses.get(firstKey + i).setEmbedding(embeddings.get(i));
                }
                embeddings = null;
                texts.clear();
                System.out.printf("Course rows processed: %d%n", rowCount);
            }

        static void embedPaperBatch
            (
                EmbeddingService service, 
                ArrayList<String> texts,
                HashMap<Integer, SearchPaper> searchPapers,
                int rowCount
            ) throws Exception {
                if (texts.isEmpty()) {
                    return;
                }
                List<List<Double>> embeddings = service.batchEmbed(texts);
                if (embeddings.size() != texts.size()) {
                    throw new IllegalStateException("Expected " + texts.size()
                            + " embeddings, received " + embeddings.size());
                }
                int firstKey = rowCount - texts.size() + 1;
                for (int i = 0; i < texts.size(); i++) {
                    searchPapers.get(firstKey + i).setEmbedding(embeddings.get(i));
                }
                texts.clear();
                System.out.printf("Paper rows processed: %d%n", rowCount);
            }
            
            static void embedProjectBatch
            (
                EmbeddingService service, 
                ArrayList<String> texts,
                HashMap<Integer, SearchProject> searchProjects,
                int rowCount
            ) throws Exception {
                if (texts.isEmpty()) {
                    return;
                }
                List<List<Double>> embeddings = service.batchEmbed(texts);
                if (embeddings.size() != texts.size()) {
                    throw new IllegalStateException("Expected " + texts.size()
                            + " embeddings, received " + embeddings.size());
                }
                int firstKey = rowCount - texts.size() + 1;
                for (int i = 0; i < texts.size(); i++) {
                    searchProjects.get(firstKey + i).setEmbedding(embeddings.get(i));
                }
                texts.clear();
                System.out.printf("Project rows processed: %d%n", rowCount);
            }
    }
