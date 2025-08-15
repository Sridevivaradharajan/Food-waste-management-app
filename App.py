import pandas as pd
import streamlit as st
import mysql.connector
import plotly.express as px

def get_db_connection():
    """Get database connection using Streamlit secrets"""
    try:
        # This will now be the only method to connect, using the secrets file
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
            port=st.secrets["mysql"]["port"]
        )
    except Exception as e:
        st.error(f"Error connecting to the database: {e}")
        st.stop()

def test_db_connection():
    """Test if database connection is working"""
    try:
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
            port=st.secrets["mysql"]["port"]
        )
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database connection test failed: {e}")
        return False

def run_query(query, params=None):
    """Run a query and return a DataFrame"""
    try:
        conn = get_db_connection()
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Query Error: {e}")
        return pd.DataFrame()

# ---------------- CRUD Operations ----------------
def create_record(table_name, inputs):
    """Generic create function for any table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Filter out empty values
        filtered_inputs = {k: v for k, v in inputs.items() if v not in [None, "", 0]}
        
        if not filtered_inputs:
            st.warning("No data to insert")
            return
            
        columns = ", ".join(filtered_inputs.keys())
        placeholders = ", ".join(["%s"] * len(filtered_inputs))
        values = tuple(filtered_inputs.values())
        
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        
        cursor.execute(query, values)
        conn.commit()
        st.success(f"Record created successfully in {table_name}")
    except mysql.connector.Error as e:
        st.error(f"Error creating record: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def update_record(table_name, record_id, inputs):
    """Generic update function for any table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get primary key for the table
        primary_keys = {
            "Food_Listings": "Food_ID",
            "Providers": "Provider_ID", 
            "Receivers": "Receiver_ID",
            "Claims": "Claim_ID"
        }
        pk = primary_keys[table_name]
        
        # Filter out empty values
        filtered_inputs = {k: v for k, v in inputs.items() if v not in [None, "", 0]}
        
        if not filtered_inputs:
            st.warning("No fields to update")
            return
        
        set_clause = ", ".join([f"{k}=%s" for k in filtered_inputs.keys()])
        values = list(filtered_inputs.values()) + [record_id]
        
        query = f"UPDATE {table_name} SET {set_clause} WHERE {pk}=%s"
        
        cursor.execute(query, values)
        conn.commit()
        if cursor.rowcount > 0:
            st.success(f"Record {record_id} updated successfully")
        else:
            st.warning(f"No record found with {pk} = {record_id}")
    except mysql.connector.Error as e:
        st.error(f"Error updating record: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def delete_record(table_name, record_id):
    """Generic delete function for any table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get primary key for the table
        primary_keys = {
            "Food_Listings": "Food_ID",
            "Providers": "Provider_ID",
            "Receivers": "Receiver_ID", 
            "Claims": "Claim_ID"
        }
        pk = primary_keys[table_name]
        
        # Handle foreign key constraints for Food_Listings
        if table_name == "Food_Listings":
            cursor.execute("DELETE FROM Claims WHERE Food_ID=%s", (record_id,))
        
        cursor.execute(f"DELETE FROM {table_name} WHERE {pk}=%s", (record_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            st.success(f"Record {record_id} deleted successfully from {table_name}")
        else:
            st.warning(f"No record found with {pk} = {record_id}")
    except mysql.connector.Error as e:
        st.error(f"Error deleting record: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# ---------------- Fetch Table Data ----------------
def fetch_table_data(table_name):
    query = f"SELECT * FROM {table_name}"
    return run_query(query)

# ---------------- Analysis Queries ----------------
def analysis_query(option, param=None):
    """Run analysis queries and return dataframe + optional figure"""
    queries = {
        "Providers & Receivers by City": """
            SELECT City,
                   (SELECT COUNT(*) FROM Providers p2 WHERE p2.City = p.City) AS Providers_Count,
                   (SELECT COUNT(*) FROM Receivers r WHERE r.City = p.City) AS Receivers_Count
            FROM Providers p
            GROUP BY City;
        """,
        "Top Food Provider Type by Quantity": """
            SELECT Type, SUM(f.Quantity) AS Total_Quantity
            FROM Providers p
            JOIN Food_Listings f ON p.Provider_ID=f.Provider_ID
            GROUP BY Type
            ORDER BY Total_Quantity DESC
            LIMIT 5;
        """,
        "Provider Contact Info by City": """
            SELECT Name, Contact, Address
            FROM Providers
            WHERE City = %s;
        """,
        "Top Receivers by Claimed Food": """
            SELECT r.Name, r.Contact, SUM(f.Quantity) AS Total_Claimed
            FROM Receivers r
            JOIN Claims c ON r.Receiver_ID=c.Receiver_ID
            JOIN Food_Listings f ON c.Food_ID=f.Food_ID
            GROUP BY r.Receiver_ID
            ORDER BY Total_Claimed DESC
            LIMIT 10;
        """,
        "Total Food Quantity Available": "SELECT SUM(Quantity) AS Total_Food_Quantity FROM Food_Listings;",
        "City with Most Food Listings": """
            SELECT p.City, COUNT(*) AS Listings_Count
            FROM Providers p
            JOIN Food_Listings f ON p.Provider_ID = f.Provider_ID
            GROUP BY p.City
            ORDER BY Listings_Count DESC
            LIMIT 1;
        """,
        "Top Food Types Available": """
            SELECT Food_Type, COUNT(*) AS Count
            FROM Food_Listings
            GROUP BY Food_Type
            ORDER BY Count DESC
            LIMIT 5;
        """,
        "Claims Count per Food Item": """
            SELECT f.Food_Name, COUNT(*) AS Claims_Count
            FROM Food_Listings f
            JOIN Claims c ON f.Food_ID = c.Food_ID
            GROUP BY f.Food_ID;
        """,
        "Top Provider by Successful Claims": """
            SELECT p.Name, COUNT(*) AS Successful_Claims
            FROM Providers p
            JOIN Food_Listings f ON p.Provider_ID = f.Provider_ID
            JOIN Claims c ON f.Food_ID = c.Food_ID
            WHERE c.Status = 'Completed'
            GROUP BY p.Provider_ID
            ORDER BY Successful_Claims DESC
            LIMIT 1;
        """,
        "Claims Status Percentage": """
            SELECT Status, 
                   COUNT(*) AS Count,
                   ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM Claims), 2) AS Percentage
            FROM Claims
            GROUP BY Status;
        """,
        "Avg Quantity Claimed per Receiver": """
            SELECT r.Name, AVG(f.Quantity) AS Avg_Quantity_Claimed
            FROM Receivers r
            JOIN Claims c ON r.Receiver_ID = c.Receiver_ID
            JOIN Food_Listings f ON c.Food_ID = f.Food_ID
            GROUP BY r.Receiver_ID;
        """,
        "Most Claimed Meal Type": """
            SELECT f.Meal_Type, COUNT(*) AS Claims_Count
            FROM Food_Listings f
            JOIN Claims c ON f.Food_ID = c.Food_ID
            GROUP BY f.Meal_Type
            ORDER BY Claims_Count DESC;
        """,
        "Total Food Donated by Provider": """
            SELECT p.Name, SUM(f.Quantity) AS Total_Quantity_Donated
            FROM Providers p
            JOIN Food_Listings f ON p.Provider_ID = f.Provider_ID
            GROUP BY p.Provider_ID
            ORDER BY Total_Quantity_Donated DESC;
        """,
        "Top Cities by Claimed Food Quantity": """
            SELECT p.City, SUM(f.Quantity) AS Total_Claimed
            FROM Providers p
            JOIN Food_Listings f ON p.Provider_ID = f.Provider_ID
            JOIN Claims c ON f.Food_ID = c.Food_ID
            WHERE c.Status='Completed'
            GROUP BY p.City
            ORDER BY Total_Claimed DESC
            LIMIT 5;
        """,
        "Providers with Most Food Listings": """
            SELECT p.Name, COUNT(f.Food_ID) AS Listings_Count
            FROM Providers p
            JOIN Food_Listings f ON p.Provider_ID = f.Provider_ID
            GROUP BY p.Provider_ID
            ORDER BY Listings_Count DESC
            LIMIT 5;
        """,
        "Expired or Soon-to-Expire Food Items": """
            SELECT Food_Name, Quantity, Expiry_Date, Location
            FROM Food_Listings
            WHERE Expiry_Date <= DATE_ADD(CURDATE(), INTERVAL 2 DAY)
            ORDER BY Expiry_Date ASC;
        """
    }
    
    # Charts configuration
    charts = {
    "Providers & Receivers by City": lambda df: px.bar(
        df, x='City', y=['Providers_Count','Receivers_Count'], 
        barmode='group', 
        title="Number of Providers and Receivers by City",
        color_discrete_sequence=px.colors.qualitative.Pastel
    ),
    "Top Food Provider Type by Quantity": lambda df: px.bar(
        df, x='Type', y='Total_Quantity', 
        title="Top Food Provider Types by Quantity",
        color='Type',
        color_discrete_sequence=px.colors.qualitative.Set2
    ),
    "Top Receivers by Claimed Food": lambda df: px.bar(
        df, x='Name', y='Total_Claimed', 
        title="Top Receivers by Claimed Food",
        color='Name',
        color_discrete_sequence=px.colors.qualitative.Vivid
    ),
    "Top Food Types Available": lambda df: px.bar(
        df, x='Food_Type', y='Count', 
        title="Top Food Types Available",
        color='Food_Type',
        color_discrete_sequence=px.colors.qualitative.Pastel1
    ),
    "Avg Quantity Claimed per Receiver": lambda df: px.bar(
        df, x='Name', y='Avg_Quantity_Claimed',
        title="Average Quantity Claimed per Receiver",
        color='Name',
        color_discrete_sequence=px.colors.qualitative.Pastel
    ),
    "Claims Status Percentage": lambda df: px.pie(
        df, names='Status', values='Percentage', 
        title="Claims Status Percentage",
        color='Status',
        color_discrete_sequence=px.colors.sequential.RdBu
    ),
     "Claims Count per Food Item": lambda df: px.bar(
        df, x='Food_Name', y='Claims_Count',
        title="Claims Count per Food Item",
        color='Food_Name',
        color_discrete_sequence=px.colors.qualitative.Set3
    ),
    "Most Claimed Meal Type": lambda df: px.bar(
        df, x='Meal_Type', y='Claims_Count', 
        title="Most Claimed Meal Type",
        color='Meal_Type',
        color_discrete_sequence=px.colors.qualitative.Dark24
    ),
    "Total Food Donated by Provider": lambda df: px.bar(
        df, x='Name', y='Total_Quantity_Donated', 
        title="Total Food Donated by Provider",
        color='Name',
        color_discrete_sequence=px.colors.qualitative.Bold
    ),
    "Top Cities by Claimed Food Quantity": lambda df: px.bar(
        df, x='City', y='Total_Claimed', 
        title="Top Cities by Claimed Food Quantity",
        color='City',
        color_discrete_sequence=px.colors.qualitative.Prism
    ),
    "Providers with Most Food Listings": lambda df: px.bar(
        df, x='Name', y='Listings_Count', 
        title="Providers with Most Food Listings",
        color='Name',
        color_discrete_sequence=px.colors.qualitative.Set3
    ),
    "Expired or Soon-to-Expire Food Items": lambda df: px.bar(
        df, x='Food_Name', y='Quantity', 
        title="Expired or Soon-to-Expire Food Items",
        color='Food_Name',
        color_discrete_sequence=px.colors.sequential.Agsunset
    )
}
    
    if option in queries:
        df = run_query(queries[option], params=(param,) if param else None)
        fig = charts[option](df) if option in charts and not df.empty else None
        return df, fig

    return None, None

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Food Wastage Management System", layout="wide")

# ---------------- Helper Function for Centered Headers ----------------
def centered_header(text, level=1, emoji=""):
    st.markdown(f"<h{level} style='text-align:center;'>{emoji} {text}</h{level}>", unsafe_allow_html=True)

# Check database connection at startup
if not test_db_connection():
    st.error("Cannot connect to database. Please check your configuration.")
    st.info("""
    **For Streamlit Cloud deployment, you need to:**
    1. Set up a cloud MySQL database (e.g., PlanetScale, Railway, or AWS RDS)
    2. Configure secrets in Streamlit Cloud with your database credentials
    3. Make sure your database tables are created and populated
    """)
    st.stop()

# Consolidated CSS styling
st.markdown("""
<style>
.stApp {
    background-image: linear-gradient(rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0.7)), 
                      url("https://images.unsplash.com/photo-1606787366850-de6330128bfc?ixlib=rb-4.0.3&auto=format&fit=crop&w=1974&q=80");
    background-size: cover;
    background-attachment: fixed;
    background-position: center;
    background-repeat: no-repeat;
}

/* Global text styling */
.stMarkdown, .stText, .stSelectbox, .stTextInput, .stNumberInput, .stDateInput, 
.stSlider, .stButton, .stDataFrame, .stInfo, .stSuccess, .stWarning, .stError,
h1, h2, h3, h4, h5, h6, p, div, span, label {
    color: #333;
    text-shadow: 1px 1px 2px rgba(255, 255, 255, 0.8);
}

/* Input styling */
.stSelectbox > div > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {
    background-color: rgba(255, 255, 255, 0.9);
    color: #333;
    border: 1px solid rgba(0, 0, 0, 0.2);
}

/* Button styling */
.stButton > button {
    background-color: rgba(0, 123, 255, 0.9);
    color: white;
    border: none;
    text-shadow: none;
    font-weight: bold;
}

.stButton > button:hover {
    background-color: rgba(0, 86, 179, 0.9);
}

/* Content containers */
.content-container {
    background-color: rgba(255, 255, 255, 0.95);
    padding: 30px;
    border-radius: 15px;
    margin: 20px 0;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    backdrop-filter: blur(10px);
}

.form-container {
    background-color: rgba(255, 255, 255, 0.9);
    border-radius: 10px;
    padding: 20px;
    margin: 15px 0;
    border: 1px solid rgba(0, 0, 0, 0.1);
}

/* Tab styling */
.stTabs [data-baseweb="tab-panel"] {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 20px;
    backdrop-filter: blur(5px);
}

/* Alert styling */
.stAlert {
    background-color: rgba(255, 255, 255, 0.9);
    border-radius: 5px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- Main Application ----------------

# Tab Navigation
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Introduction",
    "View Table & Filtering",
    "CRUD Operations",
    "SQL playground",
    "Data Analysis",
    "Contact Info",
    "User Information"
])

# ---------------- Tab 1: Introduction ----------------
with tab1:
    centered_header("Welcome to Food Wastage Management System")
    
    st.write("""
    The application will minimize food wastage by opening up communication between food providers and food seekers, since waste to one individual can be the nectar of another. Providers are able to post surplus food with specific information including quantity, meal type, expiry date, location, and receivers can be able to search and filter listings according to their own needs. The system has been equipped with CRUD functions, filtering, and analytics that will set the distribution to be done efficiently and track changes in food wastage. Through linking sought parties efficiently, it enhances sustainability, social welfare, and expansion of available resources in the best way.
    """)
    
    st.subheader("**Key Features**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("**Table Management**\n\nView, filter, and manage all database tables with advanced filtering capabilities.")
        st.warning("**SQL playground and Analytics Dashboard**\n\nSQL playground enabling various queries and 15+ SQL queries with interactive visualizations for deep insights.")
    
    with col2:
        st.info("**CRUD Operations**\n\nComplete Create, Read, Update, and Delete functionality for all records.")
        st.warning("**Contact Management**\n\nEasy access to provider and receiver contact details for direct coordination.")

# ---------------- Tab 2: View Table & Filtering ----------------
with tab2:
    centered_header("View and Filter Tables")
    
    table_name = st.selectbox("Select Table", ['Providers', 'Receivers', 'Food_Listings', 'Claims'])
    df = fetch_table_data(table_name)

    if not df.empty:
        st.subheader(f"{table_name} Table Filters")
        
        filtered_df = df.copy()
        
        # Separate columns for object (text) and number filters
        obj_cols = [col for col in df.columns if df[col].dtype == "object"]
        if obj_cols:
            st.markdown("### Text Filters")
            text_filter_cols = st.columns(3)
            for i, col in enumerate(obj_cols):
                with text_filter_cols[i % 3]:
                    val = st.text_input(f"Filter {col}", key=f"{table_name}_{col}")
                    if val:
                        filtered_df = filtered_df[filtered_df[col].str.contains(val, case=False, na=False)]
        
        num_cols = [col for col in df.columns if df[col].dtype in ["int64", "float64"]]
        if num_cols:
            st.markdown("### Numerical Filters")
            num_filter_cols = st.columns(3)
            for i, col in enumerate(num_cols):
                with num_filter_cols[i % 3]:
                    min_val, max_val = int(df[col].min()), int(df[col].max())
                    if min_val != max_val:
                        range_val = st.slider(f"{col} Range", min_val, max_val, (min_val, max_val), key=f"{table_name}_{col}")
                        filtered_df = filtered_df[(filtered_df[col] >= range_val[0]) & (filtered_df[col] <= range_val[1])]

        # Display results
        st.info(f"**Results:** {len(filtered_df)} of {len(df)} records found")
        st.dataframe(filtered_df, use_container_width=True, height=400)
    else:
        st.info(f"No data available in {table_name} table.")

# ---------------- Tab 3: CRUD Operations ----------------
with tab3:
    centered_header("CRUD Operations")

    # Table configuration
    table_fields = {
        "Food_Listings": ["Food_ID", "Food_Name", "Quantity", "Expiry_Date", "Provider_ID", "Provider_Type", "Location", "Food_Type", "Meal_Type"],
        "Providers": ["Provider_ID", "Name", "Type", "Contact", "Address", "City"],
        "Receivers": ["Receiver_ID", "Name", "Contact", "Address", "City"],
        "Claims": ["Claim_ID", "Food_ID", "Receiver_ID", "Status", "Claim_Date"]
    }
    
    primary_keys = {
        "Food_Listings": "Food_ID",
        "Providers": "Provider_ID",
        "Receivers": "Receiver_ID",
        "Claims": "Claim_ID"
    }

    col1, col2 = st.columns([1, 1])
    with col1:
        table_name = st.selectbox("Select Table", list(table_fields.keys()))
    with col2:
        crud_action = st.selectbox("Select Action", ["Create", "Update", "Delete"])

    fields = table_fields[table_name]
    pk = primary_keys[table_name]

    # Add CSS for CRUD buttons
    st.markdown(
        """
        <style>
        .crud-btn button {
            background-color: #e6f7ff !important;
            color: #000000 !important;
            border: 1px solid #91d5ff !important;
        }
        .crud-btn button:hover {
            background-color: #bae7ff !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    if crud_action == "Create":
        st.subheader(f"Create New {table_name} Record")
        with st.form(f"create_{table_name}"):
            inputs = {}
            cols = st.columns(2)
            for i, field in enumerate(fields):
                with cols[i % 2]:
                    if "ID" in field or "Quantity" in field:
                        inputs[field] = st.number_input(field, min_value=1, step=1)
                    elif "Date" in field:
                        inputs[field] = st.date_input(field)
                    else:
                        inputs[field] = st.text_input(field)
            
            with st.container():
                st.markdown('<div class="crud-btn">', unsafe_allow_html=True)
                if st.form_submit_button("Create Record", use_container_width=True):
                    create_record(table_name, inputs)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    elif crud_action == "Update":
        st.subheader(f"Update {table_name} Record")
        with st.form(f"update_{table_name}"):
            record_id = st.number_input(f"Enter {pk} to update", min_value=1, step=1)
            st.info("Fill only the fields you want to update (leave others empty)")
            
            inputs = {}
            cols = st.columns(2)
            for i, field in enumerate(fields):
                if field == pk:
                    continue
                with cols[i % 2]:
                    if "ID" in field or "Quantity" in field:
                        inputs[field] = st.number_input(field, min_value=0, step=1, value=0)
                    elif "Date" in field:
                        inputs[field] = st.date_input(field)
                    else:
                        inputs[field] = st.text_input(field)
            
            st.markdown('<div class="crud-btn">', unsafe_allow_html=True)
            if st.form_submit_button("Update Record", use_container_width=True):
                update_record(table_name, record_id, inputs)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    else:  # Delete
        st.subheader(f"Delete {table_name} Record")
        with st.form(f"delete_{table_name}"):
            record_id = st.number_input(f"Enter {pk} to delete", min_value=1, step=1)
            st.warning("This action cannot be undone!")
            
            st.markdown('<div class="crud-btn">', unsafe_allow_html=True)
            if st.form_submit_button("Delete Record", use_container_width=True):
                delete_record(table_name, record_id)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Tab 4: SQL Playground ----------------
with tab4:
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #dff0d8;
        color: #3c763d;
        border-radius: 8px;
        height: 3em;
        width: 100%;
        font-size: 16px;
        font-weight: bold;
        border: 1px solid #d6e9c6;
    }
    div.stButton > button:hover {
        background-color: #c8e5bc;
        color: #2b542c;
    }
    </style>
    """, unsafe_allow_html=True)

    centered_header("SQL Playground")

    st.info("Type any SQL query below. You can fetch data, aggregate, filter, or join tables.")
    
    user_query = st.text_area("Enter SQL Query", height=150)
    
    chart_type = st.selectbox("Optional: Choose chart type", 
                              ["None", "Bar", "Pie", "Line"])
    
    if st.button("Run Query", use_container_width=True):
        if not user_query.strip():
            st.warning("Please enter a valid SQL query.")
        else:
            with st.spinner("Executing query..."):
                try:
                    df = run_query(user_query)
                    
                    if df is not None and not df.empty:
                        st.subheader("Query Results")
                        st.dataframe(df, use_container_width=True)
                        
                        # Visualization
                        if chart_type != "None" and len(df.columns) >= 2:
                            if chart_type == "Bar":
                                st.plotly_chart(px.bar(df, x=df.columns[0], y=df.columns[1],
                                                       title="Bar Chart", color=df.columns[0],
                                                       color_discrete_sequence=px.colors.qualitative.Pastel),
                                               use_container_width=True)
                            elif chart_type == "Pie":
                                st.plotly_chart(px.pie(df, names=df.columns[0], values=df.columns[1],
                                                       title="Pie Chart",
                                                       color_discrete_sequence=px.colors.qualitative.Pastel),
                                               use_container_width=True)
                            elif chart_type == "Line":
                                st.plotly_chart(px.line(df, x=df.columns[0], y=df.columns[1],
                                                        title="Line Chart",
                                                        color_discrete_sequence=px.colors.qualitative.Set2),
                                               use_container_width=True)
                    else:
                        st.warning("Query executed but returned no data.")
                except Exception as e:
                    st.error(f"Error executing query: {e}")

# ---------------- Tab 5: Data Analysis ----------------
with tab5:
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #d9edf7;
        color: #31708f;
        border-radius: 8px;
        height: 3em;
        width: 100%;
        font-size: 16px;
        font-weight: bold;
        border: 1px solid #bce8f1;
    }
    div.stButton > button:hover {
        background-color: #c4e3f3;
        color: #245269;
    }
    </style>
    """, unsafe_allow_html=True)

    centered_header("Data Analysis Dashboard")

    query_options = [
        "Providers & Receivers by City",
        "Top Food Provider Type by Quantity",
        "Provider Contact Info by City",
        "Top Receivers by Claimed Food",
        "Total Food Quantity Available",
        "City with Most Food Listings",
        "Top Food Types Available",
        "Claims Count per Food Item",
        "Top Provider by Successful Claims",
        "Claims Status Percentage",
        "Avg Quantity Claimed per Receiver",
        "Most Claimed Meal Type",
        "Total Food Donated by Provider",
        "Top Cities by Claimed Food Quantity",
        "Providers with Most Food Listings",
        "Expired or Soon-to-Expire Food Items"
    ]

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_query = st.selectbox("Select Analysis Query", query_options)
    with col2:
        param = None
        if selected_query == "Provider Contact Info by City":
            param = st.text_input("Enter City Name")

    if st.button("Run Analysis", use_container_width=True):
        with st.spinner("Running analysis..."):
            df, fig = analysis_query(selected_query, param)

            if df is not None and not df.empty:
                st.subheader("Results")
                st.dataframe(df, use_container_width=True)

                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No data found for the selected query.")

# ---------------- Tab 6: Contact Info ----------------
with tab6:
    centered_header("Contact Information")
    
    col1, col2 = st.columns(2)
    with col1:
        entity = st.selectbox("Select Entity Type", ["Provider", "Receiver"])
    with col2:
        entity_id = st.number_input(f"Enter {entity} ID", min_value=1, step=1)
    
    if st.button("Get Contact Info", use_container_width=True):
        if entity == "Provider":
            query = "SELECT Name, Contact, Address FROM Providers WHERE Provider_ID = %s"
        else:
            query = "SELECT Name, Contact, Address FROM Receivers WHERE Receiver_ID = %s"
        
        df = run_query(query, params=(entity_id,))
        
        if not df.empty:
            st.subheader("Contact Details")
            st.dataframe(df, use_container_width=True)
        else:
            st.error(f"No {entity} found with ID {entity_id}")

# ---------------- Tab 7: User Information ----------------
with tab7:
    centered_header("About the Developer")

    # Developer Information
    st.subheader("Developer Information")
    st.write("**Name:** Sridevi V")
    st.write("**Role:** AI/ML Intern")
    st.write("**Organization:** Labmentix")

    # Project Overview
    st.subheader("Project Overview")
    st.write("""
    This Food Wastage Management System was developed as part of my AI/ML internship at Labmentix. The application demonstrates proficiency in database management, web development with Streamlit, and data visualization using modern Python libraries.
    """)

    # Technologies Used
    st.subheader("Technologies Used")
    tech_cols = st.columns(3)

    with tech_cols[0]:
        st.info("**Backend**\n- Python\n- MySQL\n- Pandas")

    with tech_cols[1]:
        st.success("**Frontend**\n- Streamlit\n- HTML/CSS\n- Plotly")

    with tech_cols[2]:
        st.warning("**Features**\n- Filtering\n- CRUD Operations \n- SQL playground and Data Analysis")


