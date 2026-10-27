package com.github.macastrogimenez.embeddingProcessor;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;


public class Main {
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
                                        ON c.id = cc.course_id;
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
                                    + "description: " + courseDescription+ "\n"
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
                                ResultSet result = statement.executeQuery(
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
                                        WHERE p.uuid = '00865963-6ad8-41ef-a860-5258d1c67b74'
                                        GROUP BY
                                            p.uuid,
                                            p.year,
                                            p.type,
                                            p.title,
                                            p.subtitle,
                                            p.abstract;
                                    """
                                )
                        ) {

                        }
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
            //texts.clear();
            System.out.printf("rows processed %d%n", rowCount);
    }
}
