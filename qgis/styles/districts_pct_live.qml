<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.44.0" styleCategories="Symbology">
 <renderer-v2 type="RuleRenderer" forceraster="0" symbollevels="0" enableorderby="0">
  <rules key="{b2c3d4e5-0000-4000-8000-000000000000}">
   <rule key="{b2c3d4e5-0001-4000-8000-000000000001}" filter="&quot;tracked&quot; = 0" label="no tracker rows" symbol="0"/>
   <rule key="{b2c3d4e5-0002-4000-8000-000000000002}" filter="&quot;tracked&quot; &gt; 0 AND &quot;pct_live&quot; &lt; 20" label="0-20% live" symbol="1"/>
   <rule key="{b2c3d4e5-0003-4000-8000-000000000003}" filter="&quot;tracked&quot; &gt; 0 AND &quot;pct_live&quot; &gt;= 20 AND &quot;pct_live&quot; &lt; 40" label="20-40%" symbol="2"/>
   <rule key="{b2c3d4e5-0004-4000-8000-000000000004}" filter="&quot;tracked&quot; &gt; 0 AND &quot;pct_live&quot; &gt;= 40 AND &quot;pct_live&quot; &lt; 60" label="40-60%" symbol="3"/>
   <rule key="{b2c3d4e5-0005-4000-8000-000000000005}" filter="&quot;tracked&quot; &gt; 0 AND &quot;pct_live&quot; &gt;= 60 AND &quot;pct_live&quot; &lt; 80" label="60-80%" symbol="4"/>
   <rule key="{b2c3d4e5-0006-4000-8000-000000000006}" filter="&quot;tracked&quot; &gt; 0 AND &quot;pct_live&quot; &gt;= 80" label="80-100%" symbol="5"/>
  </rules>
  <symbols>
   <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0">
    <layer class="SimpleFill" enabled="1" locked="0" pass="0">
     <Option type="Map">
      <Option name="color" value="208,213,221,140" type="QString"/>
      <Option name="outline_color" value="91,101,115,255" type="QString"/>
      <Option name="outline_width" value="0.26" type="QString"/>
      <Option name="style" value="solid" type="QString"/>
     </Option>
    </layer>
   </symbol>
   <symbol type="fill" name="1" alpha="1" clip_to_extent="1" force_rhr="0">
    <layer class="SimpleFill" enabled="1" locked="0" pass="0">
     <Option type="Map">
      <Option name="color" value="215,48,39,140" type="QString"/>
      <Option name="outline_color" value="91,101,115,255" type="QString"/>
      <Option name="outline_width" value="0.26" type="QString"/>
      <Option name="style" value="solid" type="QString"/>
     </Option>
    </layer>
   </symbol>
   <symbol type="fill" name="2" alpha="1" clip_to_extent="1" force_rhr="0">
    <layer class="SimpleFill" enabled="1" locked="0" pass="0">
     <Option type="Map">
      <Option name="color" value="252,141,89,140" type="QString"/>
      <Option name="outline_color" value="91,101,115,255" type="QString"/>
      <Option name="outline_width" value="0.26" type="QString"/>
      <Option name="style" value="solid" type="QString"/>
     </Option>
    </layer>
   </symbol>
   <symbol type="fill" name="3" alpha="1" clip_to_extent="1" force_rhr="0">
    <layer class="SimpleFill" enabled="1" locked="0" pass="0">
     <Option type="Map">
      <Option name="color" value="254,224,139,140" type="QString"/>
      <Option name="outline_color" value="91,101,115,255" type="QString"/>
      <Option name="outline_width" value="0.26" type="QString"/>
      <Option name="style" value="solid" type="QString"/>
     </Option>
    </layer>
   </symbol>
   <symbol type="fill" name="4" alpha="1" clip_to_extent="1" force_rhr="0">
    <layer class="SimpleFill" enabled="1" locked="0" pass="0">
     <Option type="Map">
      <Option name="color" value="166,217,106,140" type="QString"/>
      <Option name="outline_color" value="91,101,115,255" type="QString"/>
      <Option name="outline_width" value="0.26" type="QString"/>
      <Option name="style" value="solid" type="QString"/>
     </Option>
    </layer>
   </symbol>
   <symbol type="fill" name="5" alpha="1" clip_to_extent="1" force_rhr="0">
    <layer class="SimpleFill" enabled="1" locked="0" pass="0">
     <Option type="Map">
      <Option name="color" value="26,152,80,140" type="QString"/>
      <Option name="outline_color" value="91,101,115,255" type="QString"/>
      <Option name="outline_width" value="0.26" type="QString"/>
      <Option name="style" value="solid" type="QString"/>
     </Option>
    </layer>
   </symbol>
  </symbols>
 </renderer-v2>
</qgis>
