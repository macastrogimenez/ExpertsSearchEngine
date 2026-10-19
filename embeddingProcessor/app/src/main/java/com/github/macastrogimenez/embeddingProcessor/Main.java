package com.github.macastrogimenez.embeddingProcessor;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.lang.StringBuilder;
import java.util.List;
import com.github.macastrogimenez.embeddingProcessor.EmbeddingService;


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

        
        

        try (Connection connection =
                    DriverManager.getConnection(
                            url,
                            username,
                            password)) 
                    {

                        System.out.println("Connected!");

                        try (
                                Statement statement = connection.createStatement();
                                ResultSet result =
                                    statement.executeQuery("SELECT current_database(), current_user");
                            )
                            {
                                while (result.next()) {
                                    System.out.println(
                                            "Database: " + result.getString(1)
                                    );
                                    System.out.println(
                                            "User: " + result.getString(2)
                                    );
                                }
                            }

                        try(
                            Statement statement = connection.createStatement();
                            ResultSet result2 = statement.executeQuery("SELECT * FROM prod.person WHERE firstname = 'Toine'");
                        ) 
                        {
                            while (result2.next()) {
                                StringBuilder s = new StringBuilder();
                                for (int i = 1; i < 7; i++) {
                                    if (i<6){
                                        s.append(result2.getString(i)+" || ");
                                    }else{
                                        s.append(result2.getString(i));
                                        System.out.println(s.toString());
                                    }
                                }
                            }
                        }
                        
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
                            while(resultCourses.next()) {
                                rowCount++;
                                if (rowCount % 20 == 0){
                                    System.out.printf("rows processed %d \n",rowCount);
                                }
                                StringBuilder courseEmbeddingText = new StringBuilder();

                                int courseId = Integer.parseInt(resultCourses.getString(1));
                                String courseTitle = resultCourses.getString(2);
                                String courseAbstract = resultCourses.getString(3);
                                String courseDescription = resultCourses.getString(4);
                                String courseProgramme = resultCourses.getString(5);
                                String courseProfessor = resultCourses.getString(6);

                                courseEmbeddingText.append(
                                    "title: " + courseTitle
                                    + "\n"
                                    + "abstract: " + courseAbstract
                                    + "\n"
                                    + "description: " + courseDescription);

                                EmbeddingService s = new EmbeddingService();
                                List<Double> embeddedText = s.embed(courseEmbeddingText.toString(), false);

                                SearchCourse c = new SearchCourse(courseId, courseTitle, courseAbstract, courseDescription, courseProgramme, courseProfessor, embeddedText);

                                // System.out.println(c.title());
                                // System.out.println(c.courseAbstract());
                                // System.out.println(c.professorId());

                                // StringBuilder embedding = new StringBuilder();

                                // for (Double double1 : c.embedding()) {
                                //     embedding.append(double1+", ");
                                // }

                                // System.out.println("embedding: "+embedding);
                                

                                
                                // 1. retrieve data - done
                                // 2. create embedding - done 
                                // 3. store data and embedding in record
                                // 4. save record in ES
                                }
                            }
                        }
    }
}
